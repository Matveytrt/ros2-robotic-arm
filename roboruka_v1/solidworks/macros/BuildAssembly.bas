Attribute VB_Name = "BuildAssembly"
' =====================================================================
'  BuildAssembly: собирает модули M1..M6 и общую сборку руки
'  Вход:  solidworks\moduli\M*.txt   (состав модуля, генерирует scripts\moduli.py)
'         solidworks\moduli\roboruka.txt (модули по портам, поза HOME)
'  Выход: solidworks\moduli\M*.SLDASM, solidworks\roboruka_HOME.SLDASM
'  Покупные изделия: solidworks\pokupnye\*.step -> *.SLDPRT (один раз)
'  У каждого модуля начало координат на входном шарнире (см. scripts\moduli.py, PORTS)
' =====================================================================
Option Explicit

Dim swApp As Object, mu As Object
Dim swDir As String, logText As String

Sub main()
    logText = ""
    Set swApp = Application.SldWorks
    Set mu = swApp.GetMathUtility
    swDir = swApp.GetCurrentMacroPathFolder
    swDir = Left(swDir, InStrRev(swDir, "\") - 1)          ' ...\solidworks

    Dim sel As String
    sel = InputBox("Какие модули собрать? Например: M3,M6" & vbCrLf & _
                   "Пусто = все модули и общая сборка roboruka_HOME", "BuildAssembly", "")
    If StrPtr(sel) = 0 Then Exit Sub

    ConvertHW

    Dim names As New Collection, f As String, nm As Variant
    f = Dir(swDir & "\moduli\M*.txt")
    Do While f <> ""
        names.Add f
        f = Dir()
    Loop
    For Each nm In names
        If Wanted(CStr(nm), sel) Then
            BuildAsm swDir & "\moduli\" & nm, swDir & "\moduli\" & Replace(nm, ".txt", ".SLDASM")
        End If
    Next
    If Trim(sel) = "" Then BuildAsm swDir & "\moduli\roboruka.txt", swDir & "\roboruka_HOME.SLDASM"

    MsgBox "Готово" & vbCrLf & logText, vbInformation, "BuildAssembly"
End Sub

Function Wanted(fname As String, sel As String) As Boolean
    If Trim(sel) = "" Then Wanted = True: Exit Function
    Dim p As Variant
    For Each p In Split(UCase(sel), ",")
        If Left(UCase(fname), Len(Trim(p))) = Trim(p) Then Wanted = True: Exit Function
    Next
End Function

' покупные изделия: STEP -> SLDPRT, если SLDPRT ещё нет
Sub ConvertHW()
    Dim names As New Collection, f As String, nm As Variant, doc As Object, er As Long, imp As Object, outp As String
    f = Dir(swDir & "\pokupnye\*.step")
    Do While f <> ""
        names.Add f
        f = Dir()
    Loop
    For Each nm In names
        outp = swDir & "\pokupnye\" & Replace(nm, ".step", ".SLDPRT")
        If Dir(outp) = "" Then
            Set imp = swApp.GetImportFileData(swDir & "\pokupnye\" & nm)
            Set doc = swApp.LoadFile4(swDir & "\pokupnye\" & nm, "r", imp, er)
            If doc Is Nothing Then
                logText = logText & nm & ": не импортировался (" & er & ")" & vbCrLf
            Else
                doc.SaveAs3 outp, 0, 1
                swApp.CloseDoc doc.GetTitle
                logText = logText & nm & " -> SLDPRT" & vbCrLf
            End If
        End If
    Next
End Sub

Sub BuildAsm(txtPath As String, outPath As String)
    Dim txt As String, ff As Integer, lines() As String, i As Long, w() As String
    ff = FreeFile
    Open txtPath For Input As #ff
    txt = Input$(LOF(ff), ff)
    Close #ff
    lines = Split(Replace(txt, vbCr, ""), vbLf)

    ' 1) открыть все компоненты невидимо (AddComponent5 требует, чтобы файл был загружен)
    Dim paths As New Collection, mats As New Collection, full As String, typ As Long, d As Object, er As Long, wr As Long
    For i = 0 To UBound(lines)
        w = Split(Trim(lines(i)), " ")
        If UBound(w) >= 13 Then
            If w(0) = "C" Then
                full = swDir & "\" & w(1)
                typ = IIf(UCase(Right(full, 6)) = "SLDASM", 2, 1)
                swApp.DocumentVisible False, typ
                Set d = swApp.OpenDoc6(full, typ, 1, "", er, wr)
                swApp.DocumentVisible True, typ
                If d Is Nothing Then
                    logText = logText & "нет файла: " & w(1) & vbCrLf
                Else
                    paths.Add full
                    mats.Add w
                End If
            End If
        End If
    Next

    ' 2) новая сборка
    Dim outName As String
    outName = Mid(outPath, InStrRev(outPath, "\") + 1)
    swApp.CloseDoc outName
    Dim asm As Object, title As String
    Set asm = swApp.NewDocument(swApp.GetUserPreferenceStringValue(9), 0, 0, 0)   ' шаблон сборки
    title = asm.GetTitle

    ' 3) вставить компоненты и поставить их по матрицам
    Dim c As Object, k As Long, arr(15) As Double, v As Variant, comps As New Collection
    For k = 1 To paths.Count
        w = mats(k)
        Set c = asm.AddComponent5(paths(k), 0, "", False, "", 0, 0, 0)
        If c Is Nothing Then
            logText = logText & "не вставился: " & paths(k) & vbCrLf
        Else
            asm.ClearSelection2 True
            c.Select4 False, Nothing, False
            asm.UnfixComponent
            For i = 0 To 8
                arr(i) = Val(w(2 + i))
            Next
            For i = 0 To 2
                arr(9 + i) = Val(w(11 + i)) / 1000#
            Next
            arr(12) = 1#: arr(13) = 0#: arr(14) = 0#: arr(15) = 0#
            v = arr
            c.Transform2 = mu.CreateTransform(v)
            comps.Add c
        End If
    Next

    ' 4) всё зафиксировать: внутри модуля детали неподвижны относительно друг друга
    asm.ClearSelection2 True
    For Each c In comps
        c.Select4 True, Nothing, False
    Next
    asm.FixComponent
    asm.ClearSelection2 True
    asm.EditRebuild3
    asm.ShowNamedView2 "*Isometric", 7
    asm.ViewZoomtofit2

    Dim ok As Long
    ok = asm.SaveAs3(outPath, 0, 1)
    logText = logText & outName & ": " & comps.Count & " комп." & IIf(ok = 0, "", " (ошибка сохранения " & ok & ")") & vbCrLf
End Sub
