"""
Asif Khan
"""

import numpy as np
import cv2
from mtcnn.mtcnn import MTCNN
detector = MTCNN()

def one_face(frame, bbs, pointss):
    # process only one face (center ?)
    offsets = [(bbs[:,0]+bbs[:,2])/2-frame.shape[1]/2,
               (bbs[:,1]+bbs[:,3])/2-frame.shape[0]/2]
    offset_dist = np.sum(np.abs(offsets),0)
    index = np.argmin(offset_dist)
    bb = bbs[index]
    points = pointss[:,index]
    return bb, points
            
def draw_landmarks(frame, bb, points):
    # draw rectangle and landmarks on face
    cv2.rectangle(frame,(int(bb[0]),int(bb[1])),(int(bb[2]),int(bb[3])),orange,2)
    cv2.circle(frame, (points[0], points[5]), 2, (255,0,0), 2)# eye
    cv2.circle(frame, (points[1], points[6]), 2, (255,0,0), 2)
    cv2.circle(frame, (points[2], points[7]), 2, (255,0,0), 2)# nose
    cv2.circle(frame, (points[3], points[8]), 2, (255,0,0), 2)# mouth
    cv2.circle(frame, (points[4], points[9]), 2, (255,0,0), 2)
    
    w = int(bb[2])-int(bb[0])# width
    h = int(bb[3])-int(bb[1])# height
    w2h_ratio = w/h# ratio
    eye2box_ratio = (points[0]-bb[0]) / (bb[2]-points[1])
    
    cv2.putText(frame, "Width (pixels): {}".format(w), (10,30), font, font_size, red, 1)
    cv2.putText(frame, "Height (pixels): {}".format(h), (10,40), font, font_size, red, 1)
    
    if w2h_ratio < 0.7 or w2h_ratio > 0.9:
        #cv2.putText(frame, "width/height: {0:.2f}".format(w2h_ratio), (10,40), font, font_size, blue, 1)
        cv2.putText(frame, "Narrow Face", (10,60), font, font_size, red, 1)
    if eye2box_ratio > 1.5 or eye2box_ratio < 0.88:
        #cv2.putText(frame, "leye2lbox/reye2rbox: {0:.2f}".format((points[0]-bb[0]) / (bb[2]-points[1])), (10,70), font, font_size, red, 1)
        cv2.putText(frame, "Acentric Face", (10,70), font, font_size, red, 1)

def find_smile(pts):
    dx_eyes = pts[1] - pts[0]# between pupils
    dx_mout = pts[4] - pts[3]# between mouth corners
    smile_ratio = dx_mout/dx_eyes    
    return smile_ratio

def find_roll(pts):
    return pts[6] - pts[5]

def find_yaw(pts):
    le2n = pts[2] - pts[0]
    re2n = pts[1] - pts[2]
    return le2n - re2n

def find_pitch(pts):
    eye_y = (pts[5] + pts[6]) / 2
    mou_y = (pts[8] + pts[9]) / 2
    e2n = eye_y - pts[7]
    n2m = pts[7] - mou_y
    return e2n/n2m

def find_pose(points):
    X=points[0:5]
    Y=points[5:10]

    angle=np.arctan((Y[1]-Y[0])/(X[1]-X[0]))/np.pi*180
    alpha=np.cos(np.deg2rad(angle))
    beta=np.sin(np.deg2rad(angle))
    
    # compensate for roll: rotate points (landmarks) so that both the eyes are
    # alligned horizontally 
    Xr=np.zeros((5))
    Yr=np.zeros((5))
    for i in range(5):
        Xr[i]=alpha*X[i]+beta*Y[i]+(1-alpha)*X[2]-beta*Y[2]
        Yr[i]=-beta*X[i]+alpha*Y[i]+beta*X[2]+(1-alpha)*Y[2]

    # average distance between eyes and mouth
    dXtot=(Xr[1]-Xr[0]+Xr[4]-Xr[3])/2
    dYtot=(Yr[3]-Yr[0]+Yr[4]-Yr[1])/2

    # average distance between nose and eyes
    dXnose=(Xr[1]-Xr[2]+Xr[4]-Xr[2])/2
    dYnose=(Yr[3]-Yr[2]+Yr[4]-Yr[2])/2

    # relative rotation 0% is frontal 100% is profile
    Xfrontal=np.abs(np.clip(-90+90/0.5*dXnose/dXtot,-90,90))
    Yfrontal=np.abs(np.clip(-90+90/0.5*dYnose/dYtot,-90,90))

    return Xfrontal, Yfrontal


logo_size = 150
show_size = 150 # Size showed detected faces
#pixel_in_max=1000
#show_space=150

font = cv2.FONT_HERSHEY_COMPLEX # Text in video
font_size=0.4
blue=(225,0,0)
green=(0,128,0)
red=(0,0,255)
orange=(0,140,255)

total_size = np.array([750, 1400], dtype=int) # demo resolution
res_try = np.array([1080, 1920], dtype=int) # video resolution

res_max = np.zeros((2), dtype=int)
res_resize = np.zeros((2), dtype=int)
PERC_CROP_HEIGHT=0
PERC_CROP_WIDTH=0

print('initializing variables...')
minsize = 20 # minimum size of face
threshold = [ 0.6, 0.7, 0.7 ]  # three steps's threshold
factor = 0.709 # scale factor

# Recordings on/off
image_save=False
video_save = True
fps=10.
video_format=cv2.VideoWriter_fourcc('M','J','P','G')
video_max_frame=60
video_outs=[]

# video capture initialization
camera = 0#0: internal, 1: external
cap = cv2.VideoCapture(camera)

res_actual = np.zeros((1,2), dtype=int)# initialize resolution
res_actual[0,0]=cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
res_actual[0,1]=cap.get(cv2.CAP_PROP_FRAME_WIDTH)
print("camera resolution: {}".format(res_actual))

if video_save:
    video_file='video_out.avi'
    video_out=cv2.VideoWriter(video_file, video_format, fps, (640,480))

while (True): 
    
    rets, frames = cap.read()
    if not (rets):
        break
    frame = np.array(frames)
    frame = cv2.flip(frame,1)
    frame_show=np.ones((total_size[0],total_size[1],3),dtype='uint8')*255    
    res_crop = np.asarray(frame.shape)[0:2]         
    
    bbs_all, pointss_all = detector.detect_faces(frame)# face detection
   
    bbs = bbs_all.copy()
    pointss = pointss_all.copy()
    
    if len(bbs_all) > 0:# if at least one face is detected
        #process only one face (center ?)  
        bb,points = one_face(frame, bbs, pointss)
        
        draw_landmarks(frame, bb, points)# draw land marks on face   
        
        cv2.putText(frame, "Roll: {0:.2f} (-50 to +50)".format(find_roll(points)), (10,90), font, font_size, red, 1)  
        cv2.putText(frame, "Yaw: {0:.2f} (-100 to +100)".format(find_yaw(points)), (10,100), font, font_size, red, 1)
        cv2.putText(frame, "Pitch: {0:.2f} (0 to 4)".format(find_pitch(points)), (10,110), font, font_size, red, 1)
        #cv2.putText(frame, "smiles: {}, neutrals: {}, idframes: {}".format(Nsmiles, Nneutrals, Nframesperid), (10,460), font, font_size, blue, 1)
        Xfrontal, Yfrontal = find_pose(points)
        cv2.putText(frame, "Xfrontal: {0:.2f}".format(Xfrontal), (10,130), font, font_size, red, 1)
        cv2.putText(frame, "Yfrontal: {0:.2f}".format(Yfrontal), (10,140), font, font_size, red, 1)
        
        smile_ratio = find_smile(points) 
        if smile_ratio > 0.9:
            cv2.putText(frame, "Expression: Smile", (10,160), font, font_size, green, 1)
        else:
            cv2.putText(frame, "Expression: Neutral", (10,160), font, font_size, green, 1)
            
    else:
        cv2.putText(frame_show, 'no face', (10,logo_size+200), font, font_size, blue, 2)
                
    res_max[0]=total_size[0]#-show_size
    res_max[1]=total_size[1]-2*logo_size
    
    res_resize[1]=res_max[1]
    res_resize[0]=res_max[1]/res_crop[1]*res_crop[0]

    if  res_resize[0]>res_max[0]:
        res_resize[0]=res_max[0]
        res_resize[1]=int(res_max[0]/res_crop[0]*res_crop[1]/2)*2

    frame_resize = cv2.resize(frame,(res_resize[1],res_resize[0]), interpolation = cv2.INTER_LINEAR)    
    space_vert=(total_size[1]-res_resize[1]) // 2 

    frame_show[:frame_resize.shape[0],space_vert:-space_vert,:]=frame_resize 
    
    cv2.putText(frame_show, 'q: quit', (10,50), font, font_size, blue, 2)    
    cv2.imshow('Pose Detection - MTCNN',frame_show)    
    
    if video_save:
        video_out.write(frame)        
        
    key_pressed = cv2.waitKey(1) & 0xFF
    option=[]
    options=['Quit']
    if key_pressed == ord('q'):
        break

cap.release()

if video_save:
    video_out.release()

cv2.destroyAllWindows()


