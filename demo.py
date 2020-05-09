#! /usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division, print_function, absolute_import

from timeit import time
import warnings
import cv2
import numpy as np
from PIL import Image
from yolo import YOLO

from deep_sort import preprocessing
from deep_sort import nn_matching
from deep_sort.detection import Detection
from deep_sort.tracker import Tracker
from tools import generate_detections as gdet
import imutils.video
from videocaptureasync import VideoCaptureAsync
from tools.time_utils import get_current_ms


def main(yolo):
    # Definition of the parameters
    max_cosine_distance = 0.3
    nn_budget = None
    nms_max_overlap = 1.0

    # Deep SORT
    model_filename = 'model_data/mars-small128.pb'
    encoder = gdet.create_box_encoder(model_filename, batch_size=1)

    metric = nn_matching.NearestNeighborDistanceMetric("cosine", max_cosine_distance, nn_budget)
    tracker = Tracker(metric)

    writeVideo_flag = True
    asyncVideo_flag = False
    showImg_flag = True

    file_path = 'C:\\Users\\Divided\\Desktop\\test_video.mp4'
    if asyncVideo_flag:
        video_capture = VideoCaptureAsync(file_path)
    else:
        video_capture = cv2.VideoCapture(file_path)

    if asyncVideo_flag:
        video_capture.start()

    if writeVideo_flag:
        if asyncVideo_flag:
            w = int(video_capture.cap.get(3))
            h = int(video_capture.cap.get(4))
        else:
            w = int(video_capture.get(3))
            h = int(video_capture.get(4))
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter('output_yolov4.avi', fourcc, 30, (w, h))
        frame_index = -1

    fps = 0.0
    fps_imutils = imutils.video.FPS().start()

    while True:
        preprocess_time_start = get_current_ms()
        ret, frame = video_capture.read()  # frame shape 640*480*3
        if ret != True:
            break

        t1 = time.time()

        image = Image.fromarray(frame[..., ::-1])  # bgr to rgb
        preprocess_time = get_current_ms() - preprocess_time_start
        # print("Preprocessing time:\t{}".format(preprocess_time))

        detection_time_start = get_current_ms()
        boxs = yolo.detect_image(image)[0]
        confidence = yolo.detect_image(image)[1]

        detection_time = get_current_ms() - detection_time_start
        # print("Detection time:\t{}".format(detection_time))

        features = encoder(frame, boxs)

        detections = [Detection(bbox, confidence, feature) for bbox, confidence, feature in
                      zip(boxs, confidence, features)]

        nms_start_time = get_current_ms()
        # Run non-maxima suppression.
        boxes = np.array([d.tlwh for d in detections])
        scores = np.array([d.confidence for d in detections])
        indices = preprocessing.non_max_suppression(boxes, nms_max_overlap, scores)
        detections = [detections[i] for i in indices]

        nms_time = get_current_ms() - nms_start_time
        # print("NMS time:\t{}".format(nms_time))

        tracker_start_time = get_current_ms()
        # Call the tracker
        tracker.predict()
        tracker.update(detections)

        tracker_time = get_current_ms() - tracker_start_time
        # print("Tracker time:\t{}".format(tracker_time))

        postprocess_start_time = get_current_ms()

        if showImg_flag:
            for track in tracker.tracks:
                if not track.is_confirmed() or track.time_since_update > 1:
                    continue
                bbox = track.to_tlbr()
                cv2.rectangle(frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), (255, 255, 255), 2)
                cv2.putText(frame, str(track.track_id), (int(bbox[0]), int(bbox[1])), 0, 5e-3 * 200, (0, 255, 0), 2)

            for det in detections:
                bbox = det.to_tlbr()
                score = "%.2f" % round(det.confidence * 100, 2)
                cv2.rectangle(frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), (255, 0, 0), 2)
                cv2.putText(frame, score + '%', (int(bbox[0]), int(bbox[3])), 0, 5e-3 * 130, (0, 255, 0), 2)

            cv2.imshow('', frame)

        postprocess_time = get_current_ms() - postprocess_start_time
        # print("Postprocess time:\t{}".format(postprocess_time))

        if writeVideo_flag:  # and not asyncVideo_flag:
            # save a frame
            out.write(frame)
            frame_index = frame_index + 1

        fps_imutils.update()

        fps = (fps + (1. / (time.time() - t1))) / 2
        print("{}/{}/{}/{}/{}".format(preprocess_time, detection_time, nms_time, tracker_time, postprocess_time))
        print("FPS = %f" % fps)

        # Press Q to stop!
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    fps_imutils.stop()
    print('imutils FPS: {}'.format(fps_imutils.fps()))

    if asyncVideo_flag:
        video_capture.stop()
    else:
        video_capture.release()

    if writeVideo_flag:
        out.release()

    cv2.destroyAllWindows()


if __name__ == '__main__':
    main(YOLO())
