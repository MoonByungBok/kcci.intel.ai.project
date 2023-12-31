#!/usr/bin/env python3

import os
import threading
from argparse import ArgumentParser
from queue import Empty, Queue
from time import sleep

import cv2
import numpy as np
from openvino.inference_engine import IECore
from openvino.runtime import Core


from iotdemo import FactoryController, MotionDetector, ColorDetector

FORCE_STOP = False

FILE = "./resources/factory/conveyor.mp4"
CAM1 = "VIDEO:Cam1 live"
CAM2 = "VIDEO:Cam2 live"
STREAM = "/dev/video0"  #비디오 장치 이름은 스스로 찾아서 해볼 것

MODEL_PATH = "~/workspace/v2model-hw3/outputs/20230810_193341_export/openvino/openvino.xml"
#~/workspace/demodel-hw3/outputs/20230810_195106_export/openvino/openvino.xml
#~/workspace/momodel-hw3/outputs/20230810_195354_export/openvino/openvino.xml
#~/workspace/b0model-hw3/outputs/20230810_194703_export/openvino/openvino.xml
#~/workspace/v2model-hw3/outputs/20230810_193341_export/openvino/openvino.xml


#cam1 thread
def thread_cam1(q):
    # TODO: MotionDetector
    det = MotionDetector()
    det.load_preset("./motion.cfg", "default")

    # TODO: Load and initialize OpenVINO
    core = Core()
    model = core.read_model(MODEL_PATH)

    # TODO: HW2 Open video clip resources/factory/conveyor.mp4 instead of camera device.
    cap = cv2.VideoCapture(FILE)

    one_flag = True

    while not FORCE_STOP:
        sleep(0.03)
        _, frame = cap.read()
        if frame is None:
            break

        # TODO: HW2 Enqueue "VIDEO:Cam1 live", frame info
        q.put((CAM1, frame))
        
        # TODO: Motion detect
        detected = det.detect(frame)
        if detected is None:
            continue
        
        # TODO: Enqueue "VIDEO:Cam1 detected", detected info.
        q.put(("VIDEO:Cam1 detected", detected))

        # abnormal detect

        # TODO: Inference OpenVINO
        input_tensor = np.expand_dims(detected, 0)

        if one_flag is True:
            ppp = PrePostProcessor(model)
            ppp.input().tensor().set_shape(input_tensor.shape).set_element_type(Type.u8) \
                .set_layout(Layout('NHWC'))
            ppp.input().preprocess().resize(ResizeAlgorithm.RESIZE_LINEAR)
            ppp.input().model().set_layout(Layout('NCHW'))
            ppp.output().tensor().set_element_type(Type.f32)

            model = ppp.build()
            compiled_model = core.compile_model(model, "CPU")
            one_flag = False

        results = compiled_model.infer_new_request({0: input_tensor})
        predictions = next(iter(results.values()))
        probs = predictions.reshape(-1)

        print(f"{probs}")

        # TODO: Calculate ratios
        #print(f"X = {x_ratio:.2f}%, Circle = {circle_ratio:.2f}%")

        # TODO: in queue for moving the actuator 1
        if probsp[0] > 0.0:
            print("NG...")
            q.put(("PUSH", 1))
        else:
            print("OK...")


    cap.release()
    q.put(('DONE', None))
    exit()


#cam2 thread
def thread_cam2(q):
    # TODO: MotionDetector
    det = MotionDetector()
    det.load_preset("./motion.cfg", "default")

    # TODO: ColorDetector
    color = ColorDetector()
    det.load_preset("./Color.cfg", "default")

    # TODO: HW2 Open "resources/factory/conveyor.mp4" video clip
    cap = cv2.VideoCapture(FILE)

    while not FORCE_STOP:
        sleep(0.03)
        _, frame = cap.read()
        if frame is None:
            break

        # TODO: HW2 Enqueue "VIDEO:Cam1 live", frame info
        q.put((CAM2, frame))

        # TODO: Detect motion
        detected = det.detect(frame)
        if detected is None:
            continue

        # TODO: Enqueue "VIDEO:Cam1 detected", detected info.
        q.put(("VIDEO:Cam2 detected", detected))

        # TODO: Detect color
        predict = color.detect(detected)
        if not predict:
            continue

        # TODO: Compute ratio
        name, ratio = predict[0]
        ratio *= 100

        #print(f"{predict}")
        
        print(f"{name}: {ratio:.2f}%")

        # TODO: Enqueue to handle actuator 2
        if name == "blue" and ratio > .5:
            q.put(("PUSH", 2))

    cap.release()
    q.put(('DONE', None))
    exit()


def imshow(title, frame, pos=None):
    cv2.namedWindow(title)
    if pos:
        cv2.moveWindow(title, pos[0], pos[1])
    cv2.imshow(title, frame)


def main():
    global FORCE_STOP

    parser = ArgumentParser(prog='python3 factory.py',
                            description="Factory tool")

    parser.add_argument("-d",
                        "--device",
                        default=None,
                        type=str,
                        help="Arduino port")
    args = parser.parse_args()

    # TODO: HW2 Create a Queue
    q = Queue()

    # TODO: HW2 Create thread_cam1 and thread_cam2 threads and start them.
    t1 = threading.Thread(target=thread_cam1, args=(q,))
    t2 = threading.Thread(target=thread_cam2, args=(q,))

    t1.start()
    t2.start()

    with FactoryController(args.device) as ctrl:
        while not FORCE_STOP:
            if cv2.waitKey(10) & 0xff == ord('q'):
                break

            # TODO: HW2 get an item from the queue. You might need to properly handle exceptions.
            # de-queue name and data
            try: 
                name, data = q.get_nowait()
            except Empty:
                #print("frame empty")
                continue

            # TODO: HW2 show videos with titles of 'Cam1 live' and 'Cam2 live' respectively.
            if name.startswith("VIDEO:"):
                imshow(name[6:], data)

            # TODO: Control actuator, name == 'PUSH'
            elif name == "PUSH":
                ctrl.push_actuator(data)

            elif name == 'DONE':
                FORCE_STOP = True

            q.task_done()

    t1.join()
    t2.join()

    cv2.destroyAllWindows()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        os._exit()
