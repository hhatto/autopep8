# Copyright (C) 2014 Hideo Hattori, Steven Myint, Bill Wendling
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Manage how to reflow lines of code.

This is a collection of classes that manages how to reflow code. It represents
the containers (tuples, lists, dictionaries, etc.) at a very high level.

"""

import keyword
import tokenize


class ReformattedLines(object):

    """The reflowed lines of atoms.

    Each part of the line is represented as an "atom." They can be moved around
    when need be to get the optimal formatting.

    """

    class _Indent(object):

        """Represent an indentation in the atom stream."""

        def __init__(self, indent_amt):
            self._indent_amt = indent_amt

        def emit(self):
            return ' ' * self._indent_amt

        @property
        def size(self):
            return self._indent_amt

    class _Space(object):

        """Represent a space in the atom stream."""

        def emit(self):
            return ' '

        @property
        def size(self):
            return 1

    class _LineBreak(object):

        """Represent a line break in the atom stream."""

        def emit(self):
            return '\n'

        @property
        def size(self):
            return 0

    def __init__(self, max_line_length):
        self._max_line_length = max_line_length
        self._lines = []
        self._bracket_depth = 0

    def __repr__(self):
        return self.emit()

    def add_item(self, item, indent_amt):
        """Add an item to the line.

        Reflow the line to get the best formatting after the item is inserted.
        The bracket depth indicates if the item is being inserted inside of a
        container or not.

        """
        item_text = unicode(item)

        if self._lines and self._bracket_depth:
            self._prevent_default_initializer_splitting(item, indent_amt)

            if item_text in '.,)]}':
                self._split_after_delimiter(item, indent_amt)

        elif self._lines and not self.line_empty():
            if self.fits_on_current_line(len(item_text)):
                self._enforce_space(item)

            else:
                # Line break for the new item.
                self._lines.append(self._LineBreak())
                self._lines.append(self._Indent(indent_amt))

        self._lines.append(item)

        if item_text in '([{':
            self._bracket_depth += 1

        elif item_text in '}])':
            self._bracket_depth -= 1
            assert self._bracket_depth >= 0

    def add_comment(self, item):
        self._lines.append(self._Space())
        self._lines.append(self._Space())
        self._lines.append(item)

    def add_indent(self, indent_amt):
        self._lines.append(self._Indent(indent_amt))

    def add_line_break(self, indent):
        self._lines.append(self._LineBreak())
        self.add_indent(len(indent))

    def add_space_if_needed(self, curr_text, equal=False):
        prev_item = self._lines[-1] if self._lines else None

        if (
            not prev_item or isinstance(
                prev_item, (self._LineBreak, self._Indent, self._Space))
        ):
            return

        prev_prev_item = None
        for item in reversed(self._lines[:-1]):
            if isinstance(item, (self._LineBreak, self._Indent, self._Space)):
                continue
            prev_prev_item = item
            break

        prev_text = unicode(prev_item)
        prev_prev_text = unicode(prev_prev_item) if prev_prev_item else ''
        if (
            # The previous item was a keyword or identifier and the current
            # item isn't an operator that doesn't require a space.
            ((prev_item.is_keyword or prev_item.is_string or
              prev_item.is_name or prev_item.is_number) and
             (curr_text[0] not in '([{.,:}])' or
              (curr_text[0] == '=' and equal))) or

            # Don't place spaces around a '.', unless it's in an 'import'
            # statement.
            ((prev_prev_text != 'from' and prev_text[-1] != '.' and
              curr_text != 'import') and

             # Don't place a space before a colon.
             curr_text[0] != ':' and

             # Don't split up ending brackets by spaces.
             ((prev_text[-1] in '}])' and curr_text[0] not in '.,}])') or

              # Put a space after a colon or comma.
              prev_text[-1] in ':,' or

              # Put space around '=' if asked to.
              (equal and prev_text == '=') or

              # Put spaces around non-unary arithmetic operators.
              ((prev_prev_item and
                (prev_text not in '+-' and
                 (prev_prev_item.is_name or
                  prev_prev_item.is_number or
                  prev_prev_item.is_string)) and
               prev_text in ('+', '-', '%', '*', '/', '//', '**')))))
        ):
            self._lines.append(self._Space())

    def _prevent_default_initializer_splitting(self, item, indent_amt):
        """Prevent splitting between a default initializer.

        When there is a default initializer, it's best to keep it all on the
        same line. It's nicer and more readable, even if it goes over the
        maximum allowable line length. This goes back along the current line to
        determine if we have a default initializer, and, if so, to remove
        extraneous whitespaces and add a line break/indent before it if needed.

        """
        if unicode(item) == '=':
            # This is the assignment in the initializer. Just remove spaces for
            # now.
            self._delete_whitespace()
            return

        # Retrieve the last two non-whitespace items.
        prev_item = None
        prev_prev_item = None

        for prev in reversed(self._lines):
            if isinstance(prev, (self._Space, self._LineBreak, self._Indent)):
                continue
            if prev_item:
                prev_prev_item = prev
                break
            else:
                prev_item = prev

        if not prev_item or not prev_prev_item or unicode(prev_item) != '=':
            return

        self._delete_whitespace()
        prev_prev_index = self._lines.index(prev_prev_item)

        if (
            isinstance(self._lines[prev_prev_index - 1], self._Indent) or
            self.fits_on_current_line(item.size + 1)
        ):
            # The default initializer is already the only item on this line.
            # Don't insert a newline here.
            return

        # Replace the space with a newline/indent combo.
        if isinstance(self._lines[prev_prev_index - 1], self._Space):
            del self._lines[prev_prev_index - 1]

        self._lines.insert(self._lines.index(prev_prev_item),
                           self._LineBreak())
        self._lines.insert(self._lines.index(prev_prev_item),
                           self._Indent(indent_amt))

    def _split_after_delimiter(self, item, indent_amt):
        """Split the line only after a delimiter."""
        self._delete_whitespace()

        if self.fits_on_current_line(item.size):
            return

        last_space = None
        for item in reversed(self._lines):
            if isinstance(item, self._Space):
                last_space = item
                break
            if isinstance(item, (self._LineBreak, self._Indent)):
                return

        if not last_space:
            return

        self._lines.insert(self._lines.index(last_space),
                           self._LineBreak())
        self._lines.insert(self._lines.index(last_space),
                           self._Indent(indent_amt))

    def _enforce_space(self, item):
        """Enforce a space in certain situations.

        There are cases where we will want a space where normally we wouldn't
        put one. This just enforces the addition of a space.

        """
        if isinstance(self._lines[-1],
                      (self._Space, self._LineBreak, self._Indent)):
            return

        prev_item = None
        for prev in reversed(self._lines):
            if isinstance(prev, (self._Space, self._LineBreak, self._Indent)):
                continue
            prev_item = prev
            break

        if not prev_item:
            return

        item_text = unicode(item)
        prev_text = unicode(prev_item)

        # Prefer a space around a '.' in an import statement, and between the
        # 'import' and '('.
        if (
            (item_text == '.' and prev_text == 'from') or
            (item_text == 'import' and prev_text == '.') or
            (item_text == '(' and prev_text == 'import')
        ):
            self._lines.append(self._Space())

    def _delete_whitespace(self):
        while isinstance(self._lines[-1], (self._Space, self._LineBreak,
                                           self._Indent)):
            del self._lines[-1]

    def fits_on_current_line(self, item_extent):
        return self.current_size() + item_extent <= self._max_line_length

    def fits_on_empty_line(self, item_extent):
        return item_extent <= self._max_line_length

    def current_size(self):
        """The size of the current line minus the indentation."""
        size = 0
        for item in reversed(self._lines):
            size += item.size
            if isinstance(item, self._LineBreak):
                break

        return size

    def line_empty(self):
        return (self._lines and
                isinstance(self._lines[-1],
                           (self._LineBreak, self._Indent)))

    def emit(self):
        string = ''
        for item in self._lines:
            if isinstance(item, self._LineBreak):
                string = string.rstrip()
            string += item.emit()

        return string.rstrip() + '\n'

    @property
    def max_line_length(self):
        return self._max_line_length


class Atom(object):

    """The smallest unbreakable unit that can be reflowed."""

    def __init__(self, atom):
        self._atom = atom

    def __repr__(self):
        return self._atom.token_string

    def __len__(self):
        return self.size

    def reflow(self, reflowed_lines, continued_indent,
               break_after_open_bracket=False):
        if self._atom.token_type == tokenize.COMMENT:
            reflowed_lines.add_comment(self)
            return

        total_size = self.size

        if self.__repr__() not in ',:([{}])':
            # Some atoms will need an extra 1-sized space token after them.
            total_size += 1

        if (
            not reflowed_lines.fits_on_current_line(total_size) and
            not reflowed_lines.line_empty()
        ):
            # Start a new line if there is already something on the line and
            # adding this atom would make it go over the max line length.
            reflowed_lines.add_line_break(continued_indent)
        else:
            reflowed_lines.add_space_if_needed(unicode(self))

        reflowed_lines.add_item(self, len(continued_indent))

    def emit(self):
        return self.__repr__()

    @property
    def is_keyword(self):
        return keyword.iskeyword(self._atom.token_string)

    @property
    def is_string(self):
        return self._atom.token_type == tokenize.STRING

    @property
    def is_name(self):
        return self._atom.token_type == tokenize.NAME

    @property
    def is_number(self):
        return self._atom.token_type == tokenize.NUMBER

    @property
    def is_comma(self):
        return self._atom.token_string == ','

    @property
    def is_colon(self):
        return self._atom.token_string == ':'

    @property
    def size(self):
        return len(self._atom.token_string)


class Container(object):

    """Base class for all container types."""

    def __init__(self, items):
        self._items = items

    def __repr__(self):
        string = ''
        last_was_keyword = False

        for item in self._items:
            if item.is_comma:
                string += ', '
            elif item.is_colon:
                string += ': '
            else:
                item_string = unicode(item)
                if (
                    string and
                    (last_was_keyword or
                     (not string.endswith(tuple('([{,.:}]) ')) and
                      not item_string.startswith(tuple('([{,.:}])'))))
                ):
                    string += ' '
                string += item_string

            last_was_keyword = item.is_keyword
        return string

    def __iter__(self):
        for element in self._items:
            yield element

    def __getitem__(self, idx):
        return self._items[idx]

    def _get_item(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def reflow(self, reflowed_lines, continued_indent,
               break_after_open_bracket=False):
        for (index, item) in enumerate(self._items):
            prev_item = self._get_item(index - 1)
            next_item = self._get_item(index + 1)

            if isinstance(item, Atom):
                if prev_item and prev_item.is_string and item.is_string:
                    # Place consecutive string literals on separate lines.
                    reflowed_lines.add_line_break(continued_indent)

                item.reflow(reflowed_lines, continued_indent)
            else:  # isinstance(item, Container)
                item_size = item.size
                space_available = reflowed_lines.max_line_length - \
                    len(continued_indent)

                if (
                    unicode(prev_item) != '=' and
                    not reflowed_lines.line_empty() and
                    not reflowed_lines.fits_on_current_line(item_size) and
                    (reflowed_lines.fits_on_empty_line(item_size) or
                     space_available // reflowed_lines.current_size() > 4)
                ):
                    # Don't break a container if doing so means that it will
                    # align further elements way far to the right. If this
                    # happens, PEP 8 messages about visual indentations could
                    # cause the code to flow over the maximum line length.
                    #
                    # This is just a heuristic, and therefore can be improved
                    # greatly.
                    reflowed_lines.add_line_break(continued_indent)

                # Increase the continued indentation only if recursing on a
                # container.
                item.reflow(reflowed_lines, continued_indent + ' ')

            if (
                break_after_open_bracket and index == 0 and
                # Prefer to keep empty containers together instead of
                # separating them.
                unicode(item) == self.open_bracket and
                (not next_item or unicode(next_item) != self.close_bracket)
            ):
                reflowed_lines.add_line_break(continued_indent)
                break_after_open_bracket = False

    @property
    def is_string(self):
        return False

    @property
    def size(self):
        return len(self.__repr__())

    @property
    def is_keyword(self):
        return False

    @property
    def is_comma(self):
        return False

    @property
    def is_colon(self):
        return False

    @property
    def open_bracket(self):
        return None

    @property
    def close_bracket(self):
        return None


class Tuple(Container):

    """A high-level representation of a tuple."""

    @property
    def open_bracket(self):
        return '('

    @property
    def close_bracket(self):
        return ')'


class List(Container):

    """A high-level representation of a list."""

    @property
    def open_bracket(self):
        return '['

    @property
    def close_bracket(self):
        return ']'


class DictOrSet(Container):

    """A high-level representation of a dictionary or set."""

    @property
    def open_bracket(self):
        return '{'

    @property
    def close_bracket(self):
        return '}'
