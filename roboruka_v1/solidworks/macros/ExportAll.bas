Attribute VB_Name = "ExportAll"
' =====================================================================
'  ExportAll: сохраняет детали из solidworks\parts\*.SLDPRT в STEP
'  -> roboruka_v1\step_detali\NN_imya.step (поверх старых)
'  Если сейчас открыта деталь, спросит: только её или все.
'  После экспорта: python scripts\pipeline.py (DXF, листы, сборка, проверка)
' =====================================================================
Option Explicit

Dim swApp As Object
Dim swDir As String, stepDir As String, logText As String

Sub main()
    Set swApp = Application.SldWorks
    swDir = swApp.GetCurrentMacroPathFolder
    swDir = Left(swDir, InStrRev(swDir, "\") - 1)            ' ...\solidworks
    stepDir = Left(swDir, InStrRev(swDir, "\") - 1) & "\step_detali"

    Dim act As Object
    Set act = swApp.ActiveDoc
    If Not act Is Nothing Then
        If act.GetType = 1 Then
            If MsgBox("Экспортировать только открытую деталь " & act.GetTitle & "?" & vbCrLf & _
                      "Нет = экспортировать все детали из solidworks\parts", vbYesNo + vbQuestion, "ExportAll") = vbYes Then
                act.Save3 1, 0, 0
                ExportDoc act
                MsgBox logText, vbInformation, "ExportAll"
                Exit Sub
            End If
        End If
    End If

    Dim f As String, doc As Object, er As Long, wr As Long, n As Long
    f = Dir(swDir & "\parts\*.SLDPRT")
    Do While f <> ""
        If Left(f, 1) <> "~" Then
            Set doc = swApp.OpenDoc6(swDir & "\parts\" & f, 1, 1, "", er, wr)
            If Not doc Is Nothing Then
                ExportDoc doc
                n = n + 1
                swApp.CloseDoc doc.GetTitle
            Else
                logText = logText & f & ": не открылась (" & er & ")" & vbCrLf
            End If
        End If
        f = Dir()
    Loop
    MsgBox "STEP: " & n & " дет." & vbCrLf & logText, vbInformation, "ExportAll"
End Sub

Sub ExportDoc(doc As Object)
    Dim nm As String, p As String, ok As Long
    p = doc.GetPathName
    nm = Mid(p, InStrRev(p, "\") + 1)
    nm = Left(nm, InStrRev(nm, ".") - 1)
    ok = doc.SaveAs3(stepDir & "\" & nm & ".step", 0, 2 + 1)     ' копия, без вопросов
    logText = logText & nm & IIf(ok = 0, " -> STEP", " ОШИБКА " & ok) & vbCrLf
End Sub
