Attribute VB_Name = "BuildParts"
' =====================================================================
'  BuildParts: строит нативные детали SolidWorks из solidworks\data\*.txt
'  Дерево каждой детали:
'     Eskiz_kontur  -> Plastina    (бобышка на толщину T3 или T5)
'     Eskiz_otverstiya -> Otverstiya (вырез насквозь)
'  Глобальные переменные (T3, T5, D_M3, D_M2 ...) берутся из solidworks\params.txt
'  Результат: solidworks\parts\NN_imya.SLDPRT
'  Запуск: Инструменты > Макрос > Выполнить > BuildParts.swp
' =====================================================================
Option Explicit

Dim swApp As Object
Dim swDir As String
Dim logText As String

Sub main()
    logText = ""
    Set swApp = Application.SldWorks
    swDir = swApp.GetCurrentMacroPathFolder
    swDir = Left(swDir, InStrRev(swDir, "\") - 1)          ' ...\solidworks
    If Dir(swDir & "\parts", vbDirectory) = "" Then MkDir swDir & "\parts"

    Dim sel As String
    sel = InputBox("Номера деталей через запятую, например 09,20" & vbCrLf & _
                   "Пусто = все детали со статусом gen" & vbCrLf & _
                   "(детали manual строятся только если указать их номер явно)", "BuildParts", "")
    If StrPtr(sel) = 0 Then Exit Sub

    Dim oldInput As Boolean
    oldInput = swApp.GetUserPreferenceToggle(10)          ' swInputDimValOnCreate
    swApp.SetUserPreferenceToggle 10, False

    Dim f As String, n As Long
    f = Dir(swDir & "\data\*.txt")
    Do While f <> ""
        If Wanted(f, sel) Then
            BuildOne swDir & "\data\" & f, (sel <> "")
            n = n + 1
        End If
        f = Dir()
    Loop

    swApp.SetUserPreferenceToggle 10, oldInput
    MsgBox "Готово: " & n & " дет." & vbCrLf & logText, vbInformation, "BuildParts"
End Sub

Function Wanted(fname As String, sel As String) As Boolean
    If Trim(sel) = "" Then Wanted = True: Exit Function
    Dim p As Variant
    For Each p In Split(sel, ",")
        If Left(fname, 2) = Format(Val(Trim(p)), "00") Then Wanted = True: Exit Function
    Next
    Wanted = False
End Function

Function FrontPlane(doc As Object) As Object
    Dim ft As Object
    Set ft = doc.FirstFeature
    Do While Not ft Is Nothing
        If ft.GetTypeName2 = "RefPlane" Then Set FrontPlane = ft: Exit Function
        Set ft = ft.GetNextFeature
    Loop
End Function

Function ParamLines() As Collection
    Dim c As New Collection, ff As Integer, ln As String
    ff = FreeFile
    Open swDir & "\params.txt" For Input As #ff
    Do While Not EOF(ff)
        Line Input #ff, ln
        ln = Replace(Trim(ln), "mm", "")
        If Left(ln, 1) = """" Then c.Add ln
    Loop
    Close #ff
    Set ParamLines = c
End Function

Function M(s As String) As Double
    M = Val(s) / 1000#                                    ' мм -> м (API работает в метрах)
End Function

Sub BuildOne(path As String, explicitSel As Boolean)
    Dim lines() As String, txt As String, ff As Integer
    ff = FreeFile
    Open path For Input As #ff
    txt = Input$(LOF(ff), ff)
    Close #ff
    lines = Split(Replace(txt, vbCr, ""), vbLf)

    Dim pname As String, tvar As String, tval As Double, status As String
    Dim i As Long, w() As String
    For i = 0 To 2
        w = Split(lines(i), " ")
        Select Case w(0)
            Case "PART": pname = w(2)
            Case "THICK": tvar = w(1): tval = M(w(2))
            Case "STATUS": status = w(1)
        End Select
    Next
    If status = "manual" And Not explicitSel Then logText = logText & pname & ": manual, пропущена" & vbCrLf: Exit Sub

    Dim outPath As String
    outPath = swDir & "\parts\" & pname & ".SLDPRT"
    swApp.CloseDoc pname & ".SLDPRT"

    Dim doc As Object, sm As Object, tmpl As String
    tmpl = swApp.GetUserPreferenceStringValue(8)          ' swDefaultTemplatePart
    Set doc = swApp.NewDocument(tmpl, 0, 0, 0)
    Set sm = doc.SketchManager

    ' ---------- эскиз контура ----------
    doc.ClearSelection2 True
    FrontPlane(doc).Select2 False, 0
    sm.InsertSketch True
    sm.AddToDB = True
    Dim mode As String
    For i = 3 To UBound(lines)
        w = Split(lines(i), " ")
        If UBound(w) < 0 Then GoTo nxt
        Select Case w(0)
            Case "SKETCH": mode = w(1)
            Case "L"
                If mode = "KONTUR" Then sm.CreateLine M(w(1)), M(w(2)), 0, M(w(3)), M(w(4)), 0
            Case "A"
                If mode = "KONTUR" Then sm.CreateArc M(w(1)), M(w(2)), 0, M(w(3)), M(w(4)), 0, M(w(5)), M(w(6)), 0, CInt(w(7))
            Case "C"
                If mode = "KONTUR" Then sm.CreateCircleByRadius M(w(1)), M(w(2)), 0, M(w(3))
        End Select
nxt:
    Next
    sm.AddToDB = False
    sm.InsertSketch True
    Dim skK As Object
    Set skK = doc.FeatureByPositionReverse(0)
    skK.Name = "Eskiz_kontur"

    doc.ClearSelection2 True
    skK.Select2 False, 0
    Dim boss As Object
    Set boss = doc.FeatureManager.FeatureExtrusion3(True, False, False, 0, 0, tval, 0.01, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False)
    If boss Is Nothing Then
        logText = logText & pname & ": ОШИБКА бобышки (контур не замкнут?)" & vbCrLf
        doc.SaveAs3 outPath, 0, 1
        Exit Sub
    End If
    boss.Name = "Plastina"

    ' ---------- эскиз отверстий ----------
    Dim eqs As New Collection, nh As Long, seg As Object, dd As Object, r As Double
    doc.ClearSelection2 True
    FrontPlane(doc).Select2 False, 0
    sm.InsertSketch True
    sm.AddToDB = True
    For i = 3 To UBound(lines)
        w = Split(lines(i), " ")
        If UBound(w) >= 4 Then
            If w(0) = "H" Then
                r = M(w(3))
                Set seg = sm.CreateCircleByRadius(M(w(1)), M(w(2)), 0, r)
                If Not seg Is Nothing Then
                    nh = nh + 1
                    doc.ClearSelection2 True
                    seg.Select4 False, Nothing
                    Set dd = doc.AddDimension2(M(w(1)) + r * 1.2, M(w(2)) + r * 1.2 + 0.002, 0)
                    If Not dd Is Nothing Then
                        dd.GetDimension2(0).Name = "d" & nh
                        If w(4) <> "-" Then eqs.Add """d" & nh & "@Eskiz_otverstiya"" = """ & w(4) & """"
                    End If
                End If
            End If
        End If
    Next
    sm.AddToDB = False
    doc.ClearSelection2 True
    On Error Resume Next
    sm.FullyDefineSketch False, True, 0, True, 0, Nothing, True, 0, Nothing, 0, 0
    On Error GoTo 0
    sm.InsertSketch True
    Dim skH As Object
    Set skH = doc.FeatureByPositionReverse(0)
    If nh > 0 Then
        skH.Name = "Eskiz_otverstiya"
        doc.ClearSelection2 True
        skH.Select2 False, 0
        Dim cut As Object
        Set cut = doc.FeatureManager.FeatureCut4(False, False, False, 1, 1, 0.01, 0.01, False, False, False, False, 0, 0, False, False, False, False, False, True, True, True, True, False, 0, 0, False, False)
        If Not cut Is Nothing Then cut.Name = "Otverstiya"
    End If

    ' ---------- глобальные переменные и уравнения ----------
    ' 1) глобальные переменные: строки из params.txt ("T5"= 5mm)
    ' 2) уравнения: толщина = T3/T5, диаметры отверстий = D_M3/D_M2
    ' 3) связь с params.txt: поменял файл -> Ctrl+Q -> деталь перестроилась
    Dim em As Object, e As Variant, pl As Variant, rc As Long
    Set em = doc.GetEquationMgr
    On Error Resume Next
    For Each pl In ParamLines()
        rc = em.Add2(em.GetCount, CStr(pl), False)
        If rc < 0 Then logText = logText & pname & ": не принял " & pl & vbCrLf
    Next
    rc = em.Add2(em.GetCount, """D1@Plastina"" = """ & tvar & """", False)
    If rc < 0 Then logText = logText & pname & ": не принял уравнение толщины" & vbCrLf
    For Each e In eqs
        rc = em.Add2(em.GetCount, CStr(e), False)
        If rc < 0 Then logText = logText & pname & ": не принял " & e & vbCrLf
    Next
    em.FilePath = swDir & "\params.txt"
    em.LinkToFile = True
    If Err.Number <> 0 Then logText = logText & pname & ": связь с params.txt: " & Err.Description & vbCrLf: Err.Clear
    On Error GoTo 0
    doc.EditRebuild3

    ' ---------- свойства и сохранение ----------
    doc.Extension.CustomPropertyManager("").Add3 "Oboznachenie", 30, Left(pname, 2), 2
    doc.Extension.CustomPropertyManager("").Add3 "Material", 30, "Orgsteklo " & Format(tval * 1000, "0") & " mm", 2
    doc.ShowNamedView2 "*Isometric", 7
    doc.ViewZoomtofit2
    Dim ok As Long
    ok = doc.SaveAs3(outPath, 0, 1)
    logText = logText & pname & ": отверстий " & nh & IIf(ok = 0, "", "  (ошибка сохранения " & ok & ")") & vbCrLf
    If Not explicitSel Then swApp.CloseDoc doc.GetTitle     ' выбранные вручную детали остаются открытыми
End Sub
