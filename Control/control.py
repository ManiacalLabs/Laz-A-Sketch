from enum import Enum
import threading

# constrain to specific range
def clamp(n, minn, maxn):
    return max(min(maxn, n), minn)

# round to a specific increment, such as 0.25
def inc_round(v, inc):
    return round(v/inc)*inc

class Modes(Enum):
    BURN = 0
    JOG = 1


class Control(object):
    def __init__(self, g, enc, spm, inc, power, speed, init, size):
        self.grbl = g
        self.enc = enc
        self.spm = spm
        self.inc = inc
        self.power = power
        self.speed = speed
        self.init = init
        self.mode = Modes.JOG
        self.lock = threading.Lock()

        self._x, self._y = 0,0  # internal use "high res" values
        self.x, self.y = 0,0  # values constrained to specific increments

        self.grbl.unlock()
        self.cfg = self.grbl.get_config()
        # self.max_x, self.max_y = 130,130

        if size:
            self.max_x, self.max_y = size[0], size[1]
        else:
            self.max_x = self.cfg['$130']
            self.max_y = self.cfg['$131']

        self.home()
        self.grbl.send(self.init)
        self.set_speed(self.speed)
        self.set_power(self.power)

        self.set_mode(Modes.JOG)


    def home(self):
        with self.lock:
            print('Homing...')
            self.x, self.y, _ = self.grbl.home()
            self._x, self._y = self.x, self.y
            print('Homing complete')

    def set_mode(self, mode):
        self.mode = mode
        with self.lock:
            if self.mode == Modes.JOG:
                self.grbl.send('M3')
                self.__send_power(0.01)
            else:
                self.grbl.send('M4')
                self.__send_power(self.power)

    def toggle_mode(self):
        if self.mode == Modes.JOG:
            self.set_mode(Modes.BURN)
        else:
           self.set_mode(Modes.JOG)

    def set_speed(self, speed):
        self.speed = speed
        with self.lock:
            self.grbl.send('F{}'.format(self.speed))

    def __send_power(self, power):
        self.grbl.send('S{}'.format(1000*power))

    def set_power(self, power):
        with self.lock:
            self.power = power
            if self.mode == Modes.BURN:
                self.__send_power(self.power)

    def check(self):
        # store previous values
        lx, ly = self.x, self.y

        # read encoder deltas
        dx, dy = self.enc.read()

        # update and constrain internal values
        self._x += (dx / self.spm)
        self._y += (dy / self.spm)
        self._x = clamp(self._x, 0, self.max_x)
        self._y = clamp(self._y, 0, self.max_y)

        # round to configured increment
        self.x = inc_round(self._x, self.inc)
        self.y = inc_round(self._y, self.inc)

        return (self.x != lx or self.y != ly)

    def move(self):
        pos ='X{0:.2f}Y{1:.2f}'.format(self.x, self.y)
        cmd = 'G1 {}'.format(pos)
        with self.lock:
            self.grbl.send(cmd)