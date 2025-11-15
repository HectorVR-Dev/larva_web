from ultralytics import YOLO

class yolo_model():
    def __init__(self, yolo_V):
        self.model = YOLO(yolo_V)

    def inference(self, img, confianza=0.25):
        self.deteccion = []
        self.results = self.model(img, conf=confianza)
        for result in self.results:
            boxes = result.boxes
            for box in boxes:
                clase_id = int(box.cls)
                self.deteccion.append([result.names[clase_id],round(box.conf.item(),2)])
    
    def show(self):
        try:
            self.results[0].show()
        except:
            print('Nada que mostrar')
    
    def visual_contex(self):
        self.v_contex=""
        for obj in self.deteccion:
            self.v_contex= f"{self.v_contex}object {obj[0]} certainty {str(obj[1])[2:]}%. \n "
        return self.v_contex