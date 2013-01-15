;;; autopep8.el -- clean up python code
;
; based on js-beautify.el - http://sethmason.com/2011/04/28/jsbeautify-in-emacs.html
;
; put this in your emacs init:
;   (add-to-list 'load-path "~/dir/containing/autopep8/")
;   (require 'autopep8)
;
; to use:
; highlight some python code and 'M-x autopep8'

(defgroup autopep8 nil
  "Use autopep8 to clean up python code"
  :group 'editing)

(defcustom autopep8-args " --stdin "
  "Arguments to pass to autopep8 script"
  :type '(string)
  :group 'autopep8)

(defcustom autopep8-path "autopep8.py"
  "Path to autopep8 python file"
  :type '(string)
  :group 'autopep8)

(defun autopep8 ()
  "Beautify a region of python using autopep8"
  (interactive)
  (let ((orig-point (point)))
    (unless (mark)
      (mark-defun))
    (shell-command-on-region (point)
                             (mark)
                             (concat "python "
                                     autopep8-path
                                     autopep8-args)
                             nil t)
    (goto-char orig-point)))

(provide 'autopep8)
