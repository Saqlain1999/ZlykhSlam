#!/usr/bin/env python

import os
import sys

sys.path.append("./lib")

import cv2
import numpy as np
from display import Display
from frame import denormalize, Frame, match_frames
from pointmap import Map, Point





# main classes
mapp = None
display = None

def triangulate(pose1, pose2, pts1, pts2):
    ret = np.zeros((pts1.shape[0], 4))
    for i, p in enumerate(zip(pts1, pts2)):
        A = np.zeros((4,4))
        A[0] = p[0][0]*pose1[2] - pose1[0]
        A[1] = p[0][1]*pose1[2] - pose1[1]
        A[2] = p[1][0]*pose2[2] - pose2[0]
        A[3] = p[1][1]*pose2[2] - pose2[1]
        _, _, vt = np.linalg.svd(A)
        ret[i] =  vt[3]
    return ret

def process_frame(img):
    # (h, w) = img.shape[:2]
    # r = H/float(h)
    # dim = (int(w*r), H)
    img = cv2.resize(img, (W,H))
    print("In process Frame", W, H, K)
    frame = Frame(mapp, img, K)
    if frame.id == 0:
        return
    print(f"\n*** frame {frame.id} ***")
    
    # match with previous frame
    f1 = mapp.frames[-1]
    f2 = mapp.frames[-2]
    idx1, idx2, Rt = match_frames(f1, f2)
    f1.pose = np.dot(Rt, f2.pose)


    for i,idx in enumerate(idx2):
        if f2.pts[idx] is not None:
        # if f2.pts[idx] is not None and f1.pts[idx1[i]] is None:
            f2.pts[idx].add_observation(f1, idx1[i])

    good_pts4d = np.array([f1.pts[i] is None for i in idx1])

    # locally in front of camera
    # reject pts without enough depth
    # pts_tri_local = triangulate(Rt, np.eye(4), f1.kps[idx1], f2.kps[idx2])
    # good_pts4d &= np.abs(pts_tri_local[:, 3]) > 0.005

    pts4d = triangulate(f1.pose, f2.pose, f1.kps[idx1], f2.kps[idx2])
    good_pts4d &= np.abs(pts4d[:, 3]) > 0.005

    # homogenous 3-D coords
    # reject pts behind the camera
    pts4d /= pts4d[:, 3:]
    # good_pts4d &= pts_tri_local[:, 2] > 0

    # project into world
    # pts4d = np.dot(f1.pose, pts_tri_local.T).T
    
    
    # good_pts4d &= pts4d_lp[:, 2] > 0

    print(f"Adding: {np.sum(good_pts4d)} points")

    for i,p in enumerate(pts4d):
        if not good_pts4d[i]:
            continue
        color = img[int(round(f1.kpus[idx1[i],1])), int(round(f1.kpus[idx1[i],0]))]
        pt = Point(mapp, p[0:3], color)
        pt.add_observation(f2, idx2[i])
        pt.add_observation(f1, idx1[i])



    for pt1,pt2 in zip(f1.kps[idx1], f2.kps[idx2]):
        u1,v1 = denormalize(K, pt1)
        u2,v2 = denormalize(K, pt2)
        cv2.circle(img, (u1, v1), color=(0,255,0),radius=3)
        cv2.line(img, (u1, v1), (u2,v2), color=(255,0,0))
    
    # 2-D
    if display is not None:
        display.show(img)
    
    # Optimize the mapp
    if frame.id >= 4:
        err = mapp.optimize()
        print(f"Optimize: {err} units of error")

    # 3-D
    mapp.display()
    

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"{sys.argv[0]} <video.mp4>")
        exit(-1)
    
    
    cap = cv2.VideoCapture(sys.argv[1])

    # Creating a object of display class, it actually tas frames from video and makes it viewable using Sdl2

    # Feature Extractor Class returns good features to track using cv2.ORB, it's method extract takes image as a parameter (the same one from display class)
    
    # Camera Intrinsics Matrix
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    F = int(os.getenv("F", "525"))
    K = np.array(([F,0,W//2],[0,F,H//2],[0,0,1]))
    Kinv = np.linalg.inv(K)
    mapp = Map(K, Kinv)

    if os.getenv("D3D") is not None:
        mapp.create_viewer()

    if os.getenv("D2D") is not None:
        display = Display(W,H) 

    while cap.isOpened():
        ret, frame = cap.read()
        if ret:
            process_frame(frame)
        else:
            break
    