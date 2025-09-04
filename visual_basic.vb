Option Explicit

' === User options ===
Private Const TARGET_COUNT As Long = 5000   ' how many PNGs to insert
Private Const BATCH_SAVE As Long = 50       ' save every N images (tune for stability/speed)
Private Const PAGE_BREAK_EACH As Boolean = True ' insert a page break after each image

' Entry point with prompts (folder picker + optional A4 setup)
Public Sub Insert5000PNGs_OnePerPage()
    Dim folder As String
    If ActiveDocument Is Nothing Then
        Documents.Add
    End If

    ' Optional: set A4 with 2 cm margins (comment out if you prefer current settings)
    Call EnsureA4_2cmMargins

    folder = PickFolder("Select the folder containing PNG files")
    If Len(folder) = 0 Then Exit Sub

    ' Gather *.png files (non-recursive)
    Dim files As Collection
    Set files = ListPngFiles(folder)
    If files Is Nothing Or files.Count = 0 Then
        MsgBox "No PNG files found in: " & folder, vbExclamation
        Exit Sub
    End If

    ' Save the document once at the start (so we have a path on disk)
    If Len(ActiveDocument.Path) = 0 Then
        With Application.FileDialog(msoFileDialogSaveAs)
            .Title = "Save output .docx"
            .InitialFileName = "generated.docx"
            If .Show <> -1 Then Exit Sub
            Dim p As String: p = .SelectedItems(1)
            If LCase$(Right$(p, 5)) <> ".docx" Then p = p & ".docx"
            ActiveDocument.SaveAs2 FileName:=p, FileFormat:=wdFormatXMLDocument
        End With
    Else
        ActiveDocument.Save
    End If

    ' Do the insertion
    InsertPNGsCore files, TARGET_COUNT
End Sub

' Core routine: insert exactly targetCount images, cycling through files if needed
Private Sub InsertPNGsCore(ByVal files As Collection, ByVal targetCount As Long)
    Dim i As Long, idx As Long, inserted As Long
    Dim rng As Range
    Dim ils As InlineShape

    ' Compute text width in points (72 pt = 1 inch)
    Dim contentWidth As Single
    With ActiveDocument.PageSetup
        contentWidth = .PageWidth - .LeftMargin - .RightMargin
    End With
    If contentWidth <= 0 Then
        MsgBox "Invalid content width. Check page size/margins.", vbCritical
        Exit Sub
    End If

    ' Speed & stability: turn off screen updates, etc.
    Dim prevScreen As Boolean, prevAlerts As WdAlertLevel
    prevScreen = Application.ScreenUpdating
    prevAlerts = Application.DisplayAlerts
    Application.ScreenUpdating = False
    Application.DisplayAlerts = wdAlertsNone
    Application.StatusBar = "Starting insertion..."

    On Error GoTo Cleanup

    ' Ensure at least one paragraph exists
    If ActiveDocument.Content.StoryLength = 1 Then Selection.TypeParagraph

    idx = 1
    For i = 1 To targetCount
        ' Insert at end of document
        Set rng = ActiveDocument.Range(Start:=ActiveDocument.Content.End - 1, _
                                       End:=ActiveDocument.Content.End - 1)

        ' Cycle through provided files
        If idx > files.Count Then idx = 1
        Dim f As String: f = CStr(files(idx))
        idx = idx + 1

        ' Add the picture as an InlineShape, embedded (not linked)
        Set ils = rng.InlineShapes.AddPicture(FileName:=f, LinkToFile:=False, SaveWithDocument:=True)

        ' Scale to text width, keep aspect ratio, center the paragraph
        On Error Resume Next
        ils.LockAspectRatio = msoTrue
        ils.Width = contentWidth
        rng.ParagraphFormat.Alignment = wdAlignParagraphCenter
        On Error GoTo 0

        inserted = inserted + 1

        ' New page for next image
        If PAGE_BREAK_EACH Then
            rng.Collapse Direction:=wdCollapseEnd
            rng.InsertBreak wdPageBreak
        Else
            ' ensure at least a paragraph separator when not breaking pages
            rng.InsertParagraphAfter
        End If

        ' Periodic save / progress
        If (inserted Mod BATCH_SAVE) = 0 Then
            ActiveDocument.Save
            Application.StatusBar = "Inserted " & inserted & " / " & targetCount & " ... File size: " & Format$(FileLen(ActiveDocument.FullName), "#,##0") & " bytes"
            DoEvents
        End If
    Next i

    ' Final save
    ActiveDocument.Save
    Application.StatusBar = "Done. Inserted " & inserted & " images. Size: " & Format$(FileLen(ActiveDocument.FullName), "#,##0") & " bytes"
    MsgBox "Done!" & vbCrLf & "Inserted: " & inserted & vbCrLf & "Saved: " & ActiveDocument.FullName, vbInformation

Cleanup:
    Application.ScreenUpdating = prevScreen
    Application.DisplayAlerts = prevAlerts
    On Error Resume Next
    Application.StatusBar = False
End Sub

' Set page to A4 and margins to 2 cm (optional)
Private Sub EnsureA4_2cmMargins()
    With ActiveDocument.PageSetup
        .PaperSize = wdPaperA4
        .TopMargin = CentimetersToPoints(2)
        .BottomMargin = CentimetersToPoints(2)
        .LeftMargin = CentimetersToPoints(2)
        .RightMargin = CentimetersToPoints(2)
    End With
End Sub

' Pick a folder (returns "" if canceled)
Private Function PickFolder(ByVal title As String) As String
    Dim fd As FileDialog
    Set fd = Application.FileDialog(msoFileDialogFolderPicker)
    fd.Title = title
    fd.AllowMultiSelect = False
    If fd.Show = -1 Then
        PickFolder = fd.SelectedItems(1)
    Else
        PickFolder = ""
    End If
End Function

' Return a Collection of *.png files (non-recursive). Maintains OS sort order.
Private Function ListPngFiles(ByVal folder As String) As Collection
    Dim c As New Collection
    Dim p As String, f As String
    p = folder
    If Right$(p, 1) <> "\" And Right$(p, 1) <> "/" Then p = p & "\"
    f = Dir$(p & "*.png")
    Do While Len(f) > 0
        c.Add p & f
        f = Dir$
    Loop
    Set ListPngFiles = c
End Function
