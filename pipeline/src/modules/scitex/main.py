import grobidAltoStuff.scitex as scitex
import os

BASE = os.path.dirname(os.path.abspath(__file__))
GROBID = os.path.join(BASE, "grobid")

INPUT = os.path.join(BASE, "scitexIn")
OUTPUT = os.path.join(BASE, "scitexOut") + os.sep


# run grobid on the entire INPUT folder.
grobidCMD = 'java -Xmx4G -jar "' + GROBID + '/grobid-core/build/libs/grobid-core-0.7.2-onejar.jar" -gH "' + GROBID + '/grobid-home" -dIn "' + INPUT + '" -dOut "' + OUTPUT + '" -exe processFullText -ignoreAssets'

os.system(grobidCMD)

# for each thing in the INPUT folder
for root, dirs, files in os.walk(INPUT):
    for file in files:
        if file.endswith(".pdf"):
            gro = OUTPUT + file[:-4] + ".tei.xml"
            alto = OUTPUT + file[:-4] + "Alto.lxml"
            sci = OUTPUT + file[:-4] + "_SciTex.xml"
            file = os.path.abspath(INPUT + "/" + file)

            # run pdfalto
            pdfAltocmd = '"' + GROBID + '/grobid-home/pdfalto/lin-64/pdfalto" -fullFontName -noLineNumbers -noImage "' + file + '" "' + alto + '"'
            os.system(pdfAltocmd)

            # run scitex
            scitex.addScript(gro, alto, sci)

            # remove grobid and pdfalto outputs
            os.system("rm " + "\"" + gro + "\"")
            os.system("rm " + "\"" + alto + "\"")
            os.system("rm " + "\"" + alto + "_metadata.xml\"")
