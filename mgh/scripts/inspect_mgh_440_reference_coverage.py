import csv
import io
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'outputs/MGH_Project/localization'))
import mgh_localizer as core
from PIL import Image,ImageDraw

with core.source_archive() as (archive, checksum):
    poses=list(csv.DictReader(io.StringIO(archive.read(core.SCAN_ID+'/odometry.csv').decode()),skipinitialspace=True))
capture=core.cv2.VideoCapture(str(core.source_video()))
selected=list(range(10500,11221,30))
sheet=Image.new('RGB',(1200,5*205),'white')
draw=ImageDraw.Draw(sheet)
for index,(ordinal,pixels) in enumerate(core.decode_selected_frames(capture,selected)):
    image,*_=core.orient_scan_image(pixels,poses[ordinal+1])
    thumbnail=Image.fromarray(image);thumbnail.thumbnail((195,175))
    x,y=(index%6)*200,(index//6)*205
    sheet.paste(thumbnail,(x,y+25))
    draw.text((x+2,y+2),f'ord {ordinal} / {core.turning_speed(poses,ordinal+1):.0f} deg/s',fill='black')
capture.release()
sheet.save(ROOT/'work/440_scan_coverage.jpg')
