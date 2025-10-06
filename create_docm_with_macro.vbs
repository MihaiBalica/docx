Set word = CreateObject("Word.Application")
word.Visible = False
Set doc = word.Documents.Add()
doc.Content.Text = "Test document with VB macro for MetaDefender scan."

' Add a simple macro
Set vbproj = doc.VBProject
Set module = vbproj.VBComponents.Add(1)
module.CodeModule.AddFromString("Sub AutoOpen()" & vbCrLf & "MsgBox ""Macro test triggered""" & vbCrLf & "End Sub")

doc.SaveAs2 "C:\TestData\Office\MacroTest.docm", 13 ' 13 = wdFormatXMLDocumentMacroEnabled
doc.Close False
word.Quit

' cscript create_docm_with_macro.vbs