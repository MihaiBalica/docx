Set xl = CreateObject("Excel.Application")
xl.Visible = False
Set wb = xl.Workbooks.Add()
wb.Sheets(1).Cells(1,1).Value = "Test Excel with macro"

Set vbproj = wb.VBProject
Set module = vbproj.VBComponents.Add(1)
module.CodeModule.AddFromString("Sub Workbook_Open()" & vbCrLf & "MsgBox ""Excel macro triggered""" & vbCrLf & "End Sub")

wb.SaveAs "C:\TestData\Office\MacroExcel.xlsm", 52 ' 52 = xlsm macro-enabled
wb.Close False
xl.Quit

' cscript create_excel_macro.vbs