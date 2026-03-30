import Jetson.GPIO as GPIO
#import RPi.GPIO as GPIO
import smbus2
import time

# Configuración GPIO
GPIO.setmode(GPIO.BOARD)

# --- CONFIGURACIÓN Y SECUENCIAS GLOBALES ---

# Delay para GPIO directo
delay = 0.003
seq = [[1, 0, 0, 0], [1, 1, 0, 0], [0, 1, 0, 0], [0, 1, 1, 0],
       [0, 0, 1, 0], [0, 0, 1, 1], [0, 0, 0, 1], [1, 0, 0, 1]]
inv = seq[::-1]

# Delay para I2C
delay_I2C = 0.003
# Secuencia base (lógica 1-4). Se desplazará (shift) dentro de la clase.
seq_base = [0x01, 0x03, 0x02, 0x06, 0x04, 0x0C, 0x08, 0x09]
inv_base = seq_base[::-1]

class version:
    def __init__(self):
        print("Larva-Control Version: 0.0.3 (Integrated PCF8574)")

# --- CLASES Gestoras ---
class PCF8574_Manager:
    """
    Esta clase mantiene el estado global de los 8 pines del PCF8574.
    Evita que el motor borre al potenciómetro y viceversa.
    """
    def __init__(self, i2c_port=7, addr=0x20):
        self.bus = smbus2.SMBus(i2c_port)
        self.addr = addr
        self.current_state = 0x00 # Estado inicial (HIGH por defecto en PCF)
        # Escribimos el estado inicial
        try:
            self.bus.write_byte(self.addr, self.current_state)
        except Exception as e:
            print(f"Error inicializando I2C: {e}")

    def update_bits(self, value, mask):
        """
        :param value: El valor de los bits que queremos poner (ej. paso del motor)
        :param mask: Qué bits se permite tocar (ej. 0x78 para motor, 0x07 para pot)
        """
        # 1. Borrar solo los bits de la máscara en el estado actual
        self.current_state &= ~mask
        
        # 2. Poner los nuevos bits (asegurando que no se salgan de la máscara)
        self.current_state |= (value & mask)
        
        # 3. Escribir al hardware
        try:
            self.bus.write_byte(self.addr, self.current_state)
        except OSError:
            pass # Ignorar errores puntuales de bus para no detener el script

class LenteController:
    def __init__(self, motor_instance):
        """
        :param motor_instance: Un objeto ya creado de StepMotor o StepMotor_I2C
        """
        self.motor = motor_instance 
        # Asumimos que el motor ya maneja su propio contador interno 'cont'

    def set_lente(self, lente):
        posiciones_lentes = {1: 0, 2: 100, 3: 200, 4: 300, 5: 400}
        
        if lente in posiciones_lentes:
            objetivo = posiciones_lentes[lente]
            
            # Accedemos a la variable 'cont' del motor que le pasamos
            pasos_a_mover = objetivo - self.motor.cont 
            
            direccion = 1 if pasos_a_mover > 0 else -1
            
            # Usamos el método .step() del motor genérico
            self.motor.step(abs(pasos_a_mover), direccion)
            print(f"Lente {lente} alcanzado.")
        else:
            print(f"Lente {lente} no reconocido.")

class LightController:
    def __init__(self, potenciometro_instance):
        """
        :param potenciometro_instance: Objeto de la clase PotenciometerX9C ya instanciado
        """
        self.pot = potenciometro_instance
        
        # Diccionario de perfiles: {Nivel: Porcentaje (0.0 a 1.0)}
        self.perfiles = {
            1: 0.0,   # 0%   -> Apagado
            2: 0.25,  # 25%  -> Bajo
            3: 0.50,  # 50%  -> Medio
            4: 0.75,  # 75%  -> Alto
            5: 1.0    # 100% -> Máximo
        }

    def set_profile(self, perfil):
        """
        Establece el brillo basado en un perfil discreto (1 a 5).
        """
        if perfil in self.perfiles:
            target_percentage = self.perfiles[perfil]
            
            # Calculamos los pasos reales basados en la capacidad del hardware
            # Ejemplo: 0.50 * 99 = 49.5 -> int(49) pasos
            target_step = int(target_percentage * self.pot.MAX_STEPS)
            
            print(f"⚡ Perfil {perfil} seleccionado ({int(target_percentage*100)}%) -> Ajustando a paso {target_step}")
            self.pot.set_position(target_step)
            
        else:
            print(f"⚠️ Error: El perfil '{perfil}' no existe. Use valores del 1 al 5.")

    def turn_off(self):
        """Atajo para apagar la luz (Perfil 1)"""
        self.set_profile(1)

    def turn_max(self):
        """Atajo para brillo máximo (Perfil 5)"""
        self.set_profile(5)
   
# --- CLASES GPIO (DIRECTO) ---

class StepMotor: 
    # Control directo por GPIO de la Jetson/RPi
    def __init__(self, pines, fc = None, dir_orig=None):
        self.inf = f'StepMotor_GPIO{pines}_FC{fc}]'
        self.pines = pines
        self.cont = 0
        self.fc = fc
        self.dir_orig = dir_orig
        
        for pin in self.pines:
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

        if self.fc is not None:
            GPIO.setup(self.fc, GPIO.IN)
        
    def step(self, pasos, direccion):
        print(f"⟳ {self.inf} Moviendo {pasos} pasos Dir:{direccion}")
        # Seleccionar secuencia según dirección
        current_seq = seq if direccion == 1 else inv
        
        for i in range(pasos):
            # Verificar FC si existe
            if self.fc is not None:
                # Si tocamos FC y tratamos de ir hacia el origen (dir_orig), parar
                if GPIO.input(self.fc) and direccion == self.dir_orig:
                     print(f"El {self.inf} fue detenido por su FC")
                     print(self.cont)
                     return

            # Mover
            if direccion == 1: self.cont += 1
            else: self.cont -= 1
            
            for h in range(8):
                for pin in range(4):
                    GPIO.output(self.pines[pin], current_seq[h][pin])
                time.sleep(delay)
        self.off()

    def origen(self):
        if self.fc is not None and self.dir_orig is not None:
            print(f"Yendo a origen {self.inf}...")
            # Mientras el FC no esté presionado (asumiendo pull-up o lógica active low)
            # Ajustar la lógica del while según tu sensor (1 o 0)
            while GPIO.input(self.fc) != 0: 
                # Mover un paso en la dirección de origen
                paso_seq = seq if self.dir_orig == 1 else inv
                for h in range(8):
                    for pin in range(4):
                        GPIO.output(self.pines[pin], paso_seq[h][pin])
                    time.sleep(delay)
            self.reset()
        else:
            print("No se ha definido final de carrera u origen")
        
        self.off()

    def off(self):
        for pin in range(4):
            GPIO.output(self.pines[pin],0)
            time.sleep(delay)

    def reset(self):
        self.cont = 0

# --- CLASES I2C (PCF8574) ---

class StepMotor_I2C: 
    def __init__(self, pcf_manager, fc=None, dir_orig=1):
        """
        :param pcf_manager: Instancia de PCF8574_Manager
        :param fc: Pin GPIO (físico) del final de carrera
        """
        self.manager = pcf_manager
        self.cont = 0
        self.fc = fc
        self.dir_orig = dir_orig
        
        # MÁSCARA DEL MOTOR: Pines P3, P4, P5, P6
        # Binary: 01111000 = 0x78
        self.MOTOR_MASK = 0x78 

        if fc is not None:
            GPIO.setup(self.fc, GPIO.IN)
    
    def _write_step(self, step_byte):
        # Desplazamos el byte de secuencia 3 lugares a la izquierda
        # Porque el motor empieza en P3. 
        # Ej: 0x01 (P0) -> 0x08 (P3)
        val = step_byte << 3
        self.manager.update_bits(val, self.MOTOR_MASK)
        time.sleep(delay_I2C)

    def step(self, pasos, direccion):
        # Seleccionar la lista correcta
        current_seq = seq_base if direccion == 1 else inv_base

        for i in range(pasos):
            # Chequeo de Final de Carrera
            if self.fc is not None:
                if GPIO.input(self.fc) and direccion == self.dir_orig:
                    print("Motor I2C detenido por FC")
                    return

            if direccion == 1: self.cont += 1
            else: self.cont -= 1

            # Ejecutar secuencia de 8 micropasos
            for h in range(8):
                self._write_step(current_seq[h])
        
        self.off()

    def origen(self): 
        if self.fc is not None:
            print("Motor I2C yendo a origen...")
            target_seq = seq_base if self.dir_orig == 1 else inv_base
            
            # Asumiendo lógica del sensor (ajustar != 1 o != 0 según sensor)
            while GPIO.input(self.fc) != 1:
                for h in range(8):
                    self._write_step(target_seq[h])
            self.reset()
        else:
            print("No FC definido para Motor I2C")
        
        self.off()

    def off(self):
        self._write_step(0x00)

    def reset(self):
        self.cont = 0

class PotenciometerX9C:
    """ Control del X9C102P vía PCF8574 (P0, P1, P2) """
    def __init__(self, pcf_manager):
        self.manager = pcf_manager

        #Variable que guarda el estado local de los pines
        self._local_state = 0x07 # Todos en HIGH al inicio
        
        # Definición de bits (0, 1, 2)
        self.PIN_CS  = 0 
        self.PIN_INC = 1 
        self.PIN_UD  = 2
        
        # MÁSCARA DEL POTENCIOMETRO: Pines P0, P1, P2
        # Binary: 00000111 = 0x07
        self.POT_MASK = 0x07
        
        self.MAX_STEPS = 99
        self.position = 0 
        
        # Inicializar: CS=1, INC=1, UD=1
        self._set_pins(cs=1, inc=1, ud=1)
        self.reset_to_minimum() # Calibrar a 0
        self.set_position(70)   # Ir a medio camino

    def _set_pins(self, cs=None, inc=None, ud=None):
        # Leemos el estado interno actual del manager (aunque aquí lo reconstruimos)
        # Es mejor construir el valor deseado de los 3 bits
        # Pero como update_bits hace un Read-Modify-Write lógico, 
        # necesitamos saber qué valor enviar para ESTOS 3 bits.
        
        if inc is not None:
            if inc: self._local_state |= (1 << self.PIN_INC)
            else:   self._local_state &= ~(1 << self.PIN_INC)
        
        if ud is not None:
            if ud: self._local_state |= (1 << self.PIN_UD)
            else:  self._local_state &= ~(1 << self.PIN_UD)
            
        if cs is not None:
            if cs: self._local_state |= (1 << self.PIN_CS)
            else:  self._local_state &= ~(1 << self.PIN_CS)
            
        # Enviamos al manager
        self.manager.update_bits(self._local_state, self.POT_MASK)

    def _pulse_inc(self):
        self._set_pins(inc=0)
        self._set_pins(inc=1)

    def increment(self, steps):
        self._set_pins(cs=0, ud=1) # Enable, Up
        for _ in range(steps):
            if self.position >= self.MAX_STEPS: break
            self._pulse_inc()
            self.position += 1
        self._set_pins(cs=1) 

    def decrement(self, steps):
        self._set_pins(cs=0, ud=0) # Enable, Down
        for _ in range(steps):
            if self.position <= 0: break
            self._pulse_inc()
            self.position -= 1
        self._set_pins(cs=1)

    def reset_to_minimum(self):
        self._set_pins(cs=0, ud=0)
        for _ in range(105): # +100 pulsos para asegurar
            self._pulse_inc()
        self._set_pins(cs=1)
        self.position = 0

    def set_position(self, target):
        target = max(0, min(target, self.MAX_STEPS))
        diff = target - self.position
        if diff > 0: self.increment(diff)
        elif diff < 0: self.decrement(abs(diff))

def liberate():
    GPIO.cleanup()