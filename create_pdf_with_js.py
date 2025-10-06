pdf_js = r"""%PDF-1.5
1 0 obj
<< /Names [(JavaScript) 2 0 R] >>
endobj
2 0 obj
<< /S /JavaScript /JS (app.alert("PDF JS Test!");) >>
endobj
3 0 obj
<< /Type /Catalog /OpenAction 2 0 R >>
endobj
trailer
<< /Root 3 0 R >>
%%EOF
"""

import os
os.makedirs("PDF", exist_ok=True)
with open("PDF/PDF_JS_Test.pdf", "w") as f:
    f.write(pdf_js)
print("PDF with embedded JS created.")