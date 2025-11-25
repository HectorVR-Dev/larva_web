import Jetson.GPIO as GPIO
#import RPi.GPIO as GPIO
import smbus2
import time

GPIO.setmode(GPIO.BOARD)

delay = 0.003
seq = [[1, 0, 0, 0],
       [1, 1, 0, 0],
       [0, 1, 0, 0],
       [0, 1, 1, 0],
       [0, 0, 1, 0],
       [0, 0, 1, 1],
       [0, 0, 0, 1],
       [1, 0, 0, 1]]

inv = seq[::-1]

delay_I2C = 0.005
seq_I2C = [ 0x01,   # P0=1            → 0b00000001 = 0x01
            0x03,   # P0=1, P1=1      → 0b00000011 = 0x03
            0x02,   # P1=1            → 0b00000010 = 0x02
            0x06,   # P1=1, P2=1      → 0b00000110 = 0x06
            0x04,   # P2=1            → 0b00000100 = 0x04
            0x0C,   # P2=1, P3=1      → 0b00001100 = 0x0C
            0x08,   # P3=1            → 0b00001000 = 0x08
            0x09]   # P0=1, P3=1      → 0b00001001 = 0x09

inv_I2C = seq_I2C[::-1]

class version:
    def __init__(self):
        print("Larva-Control Version: 0.0.2")

class StepMotor: 
    # Clase para controlar motores paso a paso
    # pines: lista de pines del motor
    # fc: pin de fin de carrera (opcional)(pull-up)
    # Esta clse permite controlar motores paso a paso
    # con la posibilidad de vincularlo a un fin de carrera

    def __init__(self, pines, fc = None, dir_orig=None):
        self.inf = f'StepMotor_GPIO{pines}_FC{fc}]'
        self.pines = pines
        self.cont = 0
        self.fc = False
        
        for pin in self.pines:
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

        self.fc = fc

        if self.fc is not None:
            GPIO.setup(self.fc, GPIO.IN)
        
        self.dir_orig = dir_orig
        
    def step(self, pasos, direccion):
        print(f"⟳ {self.inf} Moviendo {pasos} pasos en dirección {direccion}")
        if self.fc is not None:
            if direccion == 1:
                for i in range(pasos):
                    if not GPIO.input(self.fc):
                        self.cont += 1
                        for h in range(8):
                            for pin in range(4):
                                GPIO.output(self.pines[pin], seq[h][pin])
                                time.sleep(delay)
                    
                    elif direccion != self.dir_orig:
                        self.cont += 1
                        for h in range(8):
                            for pin in range(4):
                                GPIO.output(self.pines[pin], seq[h][pin])
                                time.sleep(delay)

                    else:
                        print(f"El {self.inf} fue detenido por su fC")
                        return
                    
            
            elif direccion == -1:
                for i in range(pasos):
                    if  not GPIO.input(self.fc):
                        self.cont -= 1
                        for h in range(8):
                            for pin in range(4):
                                GPIO.output(self.pines[pin], inv[h][pin])
                                time.sleep(delay)

                    elif direccion != self.dir_orig:
                        self.cont -= 1
                        for h in range(8):
                            for pin in range(4):
                                GPIO.output(self.pines[pin], inv[h][pin])
                                time.sleep(delay)
                    else:
                        print(f"El {self.inf} fue detenido por su fC")
                        return
        else:
            if direccion == 1:
                for i in range(pasos):
                    self.cont += 1
                    for h in range(8):
                        for pin in range(4):
                            GPIO.output(self.pines[pin], seq[h][pin])
                            time.sleep(delay)

            elif direccion == -1:
                for i in range(pasos):
                    self.cont -= 1
                    for h in range(8):
                        for pin in range(4):
                            GPIO.output(self.pines[pin], inv[h][pin])
                            time.sleep(delay)

    def origen(self): #Funciona Testeado
        if self.fc is not None:
            if self.dir_orig == 1:
                while GPIO.input(self.fc) != 1:
                    for h in range(8):
                        for pin in range(4):
                            GPIO.output(self.pines[pin], seq[h][pin])
                            time.sleep(delay)
            if self.dir_orig == -1:
                while GPIO.input(self.fc) != 1:
                    for h in range(8):
                        for pin in range(4):
                            GPIO.output(self.pines[pin], inv[h][pin])
                            time.sleep(delay)
            #self.reset()

        else:
            print("No se ha definido final de carrera, no se puede regresar al origen")

    def reset(self):
        self.cont = 0

class StepMotor_I2C: 
    # Clase para controlar motores paso a paso via I2C con PCF8574
    # pines: lista de pines del motor
    # fc: pin de fin de carrera (opcional)(pull-up)
    # Esta clse permite controlar motores paso a paso
    # con la posibilidad de vincularlo a un fin de carrera

    def __init__(self, pines, fc = None, dir_orig=1, i2c_port_num=7, addr=0x20):
        self.pines = pines
        self.cont = 0
        self.fc = fc
        self.dir_orig = dir_orig
        self.i2c_port_num = i2c_port_num
        self.addr = addr
        self.bus = smbus2.SMBus(i2c_port_num)
        self.bus.write_byte(self.addr, 0x00)  # Inicializar todo en LOW

        if fc is not None:
            GPIO.setup(self.fc, GPIO.IN)
    
    def step(self, pasos, direccion):

        if self.fc is not None:
            if direccion == 1:
                for i in range(pasos):
                    if not GPIO.input(self.fc):
                        self.cont += 1
                        for h in range(8):
                            self.bus.write_byte(self.addr, seq_I2C[h])
                            time.sleep(delay_I2C)
                    
                    elif direccion != self.dir_orig:
                        self.cont += 1
                        for h in range(8):
                            self.bus.write_byte(self.addr, seq_I2C[h])
                            time.sleep(delay_I2C)

                    else:
                        print(f"El {self.inf} fue detenido por su fC")
                        return
                    
            
            elif direccion == -1:
                for i in range(pasos):
                    if  not GPIO.input(self.fc):
                        self.cont -= 1
                        for h in range(8):
                            self.bus.write_byte(self.addr, inv_I2C[h])
                            time.sleep(delay_I2C)

                    elif direccion != self.dir_orig:
                        self.cont -= 1
                        for h in range(8):
                            self.bus.write_byte(self.addr, inv_I2C[h])
                            time.sleep(delay_I2C)
                    else:
                        print(f"El {self.inf} fue detenido por su fC")
                        return
        else:
            if direccion == 1:
                for i in range(pasos):
                    self.cont += 1
                    for h in range(8):
                        self.bus.write_byte(self.addr, seq_I2C[h])
                        time.sleep(delay_I2C)

            elif direccion == -1:
                for i in range(pasos):
                    self.cont -= 1
                    for h in range(8):
                        self.bus.write_byte(self.addr, inv_I2C[h])
                        time.sleep(delay_I2C)

    def origen(self): #Funciona Testeado
        if self.fc is not None:
            if self.dir_orig == 1:
                while GPIO.input(self.fc) != 1:
                    for h in range(8):
                        for pin in range(4):
                            self.pcf.port[self.pines[pin]] = self.seq[h][pin]
                            time.sleep(delay_I2C)
            if self.dir_orig == -1:
                while GPIO.input(self.fc) != 1:
                    for h in range(8):
                        for pin in range(4):
                            self.pcf.port[self.pines[pin]] = self.inv[h][pin]
                            time.sleep(delay_I2C)
            self.reset()

        else:
            print("No se ha definido final de carrera, no se puede regresar al origen")

    def reset(self):
        self.cont = 0

class stepMotor_chLente(StepMotor):

    def __init__(self, pines, fc, dir_orig):
        super().__init__(pines, fc, dir_orig)

    def set_lente(self, lente):
        # Define la posición del motor para un lente específico
        posiciones_lentes = {
            1: 0,
            2: 100,
            3: 200,
            4: 300,
            5: 400
        }
        if lente in posiciones_lentes:
            objetivo = posiciones_lentes[lente]
            pasos_a_mover = objetivo - self.cont
            direccion = 1 if pasos_a_mover > 0 else -1
            self.step(abs(pasos_a_mover), direccion)
        else:
            print(f"Lente {lente} no reconocido.")
    
class stepMotor_chLente_I2C(StepMotor_I2C):

    def __init__(self, pines, fc, dir_orig, i2c_port_num=7, addr=0x20):
        super().__init__(pines, fc, dir_orig, i2c_port_num, addr)

    def set_lente(self, lente):
        # Define la posición del motor para un lente específico
        posiciones_lentes = {
            1: 0,
            2: 100,
            3: 200,
            4: 300,
            5: 400
        }
        if lente in posiciones_lentes:
            objetivo = posiciones_lentes[lente]
            pasos_a_mover = objetivo - self.cont
            direccion = 1 if pasos_a_mover > 0 else -1
            self.step(abs(pasos_a_mover), direccion)
        else:
            print(f"Lente {lente} no reconocido.")

class Light_var:
    def __init__(self, pines):
        self.pines = pines
        self.status = False
        for pin in self.pines:
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH)

    def encender(self, intensidad):
        if intensidad == 1:
            GPIO.output(self.pines[1], 1)
            time.sleep(0.001)
            GPIO.output(self.pines[2], 1)
            time.sleep(0.001)
            GPIO.output(self.pines[0], 0)
            self.status = True
        
        elif intensidad == 2:
            GPIO.output(self.pines[0], 1)
            time.sleep(0.001)
            GPIO.output(self.pines[2], 1)
            time.sleep(0.001)
            GPIO.output(self.pines[1], 0)
            self.status = True
        
        elif intensidad == 3:
            GPIO.output(self.pines[0], 1)
            time.sleep(0.001)
            GPIO.output(self.pines[1], 1)
            time.sleep(0.001)
            GPIO.output(self.pines[2], 0)
            self.status = True

    def apagar(self):
        for pin in self.pines:
            GPIO.output(pin, 1)
            time.sleep(0.001)
        self.status = False

    def estado(self):
        return self.status   

def liberate():
    GPIO.cleanup()
