; md2docx_clip.ahk
; ------------------
; Press Ctrl+Alt+M anywhere:
;   1. Takes current clipboard text (your copied LLM output)
;   2. Converts it via md2docx
;   3. Puts Word-native formatted content back on clipboard
;   4. Ready to Ctrl+V into Word
;
; Install AutoHotkey v2: https://www.autohotkey.com/
; Then double-click this file (or add it to shell:startup for auto-start).

#Requires AutoHotkey v2.0

^!m:: {
    ; Show a brief tooltip so you know it's working
    ToolTip("Converting clipboard via md2docx...")
    
    ; Run the converter (hidden window)
    RunWait('"C:\opt\md2docx\.venv\Scripts\python.exe" "C:\opt\md2docx\md2docx_clip.py"',, "Hide")
    
    ToolTip("Done! Ctrl+V to paste into Word.")
    Sleep(2000)
    ToolTip()   ; clear tooltip
}
