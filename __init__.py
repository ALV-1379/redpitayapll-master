
import paramiko as pa
import os
import sys
import numpy as np

HOSTNAME = '192.168.1.9'
USERNAME = 'root'
PASSWORD = 'root'
NPLL = '2'

class RedPitaya:
    register = {0x41200000: None,
                0x41200008: None,
                0x41210000: None,
                0x41210008: None,
                0x41220000: None,
                0x41220008: None,
                0x41230000: None,
                0x41300000: None,
                0x41300008: None,
                0x41310000: None,
                0x41310008: None,
                0x41320000: None,
                0x41320008: None,
                0x41330000: None}

    # Dictioanry structure: each elemt is one parameter (as written into the RP). The value is an array of the format [addr_offset, MSB, LSB]
    glob_base_addr = 0x41200000
    glob_param_dict = { 'output_1': [0, 2, 0], 
                        'output_2': [0, 5, 3],
                        'ext_pins_p': [0, 23, 16],
                        'ext_pins_n': [0, 31, 24]}
    
    pll_base_addr = [0x41200000, 0x41300000]
    pll_param_dict = {  '2nd_harm': [0, 7, 7], 
                        'pid_en':   [0, 6, 6], 
                        'w_a':      [8, 15, 8], 
                        'w_b':      [8, 7, 0], 
                        'kp':       [0x10000, 31, 0], 
                        'ki':       [0x10008, 31, 0], 
                        'f0':       [0x20000, 31, 0], 
                        'bw':       [0x20008, 31, 0], 
                        'alpha':    [0x30000, 26, 10],
                        'order':    [0x30000, 2, 0]}
     
    glob_param_values = {}
    pll_param_values = []
                
    n_pll = 1
    
    pll_parameters_keys = ['2nd_harm', 'pid_en',   'a',    'phi',  'kp',   'ki',   'f0',   'bw',   'alpha', 'order']
    glob_parameter_keys = ['output_1', 'output_2', 'ext_pins_p', 'ext_pins_n']
    
    output_options = {'PLL1': '000',
                      'PLL2': '001',
                      'PLL1 + PLL2': '010',
                      'PLL1 + IN2': '011',
                      'IN1': '100',
                      'IN2': '101',
                      'LI1_X': '110',
                      'LI2_Y': '111'}

    output_options_inv = {'000': 'PLL1',
                          '001': 'PLL2',
                          '010': 'PLL1 + PLL2',
                          '011': 'PLL1 + IN2',
                          '100': 'IN1',
                          '101': 'IN2',
                          '110': 'LI1_X',
                          '111': 'LI2_Y'}


                          
                          
    parameters = None

    def __init__(self, hostname, username='root', password='root', n_pll=1):
        self.n_pll = n_pll
        
        self.glob_param_values = {key: None for key in self.glob_param_dict}
        self.pll_param_values = {pll: {key: None for key in self.pll_param_values} for pll in range(self.n_pll)}
        
        self.client = pa.SSHClient()
        self.client.set_missing_host_key_policy(pa.AutoAddPolicy())
        self.client.load_system_host_keys()
        self.client.connect(hostname, username=username, password=password)
        self.get_all_parameters()

    def get_all_registers(self):
        for key in self.register:
            if (self.n_pll == 1) and (key >= self.pll_base_addr[1]):
                continue
            tmp = self.client.exec_command('/opt/redpitaya/bin/monitor ' + str(key))[1].read().strip()
            self.register[key] = self.__class__.hex_to_binary_string(tmp)

    def set_register(self, register):
        command = '/opt/redpitaya/bin/monitor {0} {1}'.format(str(register), self.__class__.unsigned_bitstring_to_int(self.register[register]))
        stdin, stdout, stderr = self.client.exec_command(command)

    def read_register_bitstring(self, base_addr, param_dict, key):
        addr = base_addr + param_dict[key][0]
        msb = param_dict[key][1]
        lsb = param_dict[key][2]
        if lsb == 0:
            return self.register[addr][-(msb+1):]
        else:
            return self.register[addr][-(msb+1):-(lsb)]
        
    def write_register_bitstring(self, base_addr, param_dict, key, value_dict):
        addr = base_addr + param_dict[key][0]
        msb = param_dict[key][1]
        lsb = param_dict[key][2]
        tmp = list(self.register[addr])
        if lsb == 0:
            tmp[-(msb+1):] = value_dict[key]
        else:
            tmp[-(msb+1):-(lsb)] = value_dict[key]
        self.register[addr] = "".join(tmp)
        
        
    def get_addr(self, base_addr, param_dict, key):
        return base_addr + param_dict[key][0]
        
    def get_all_parameters(self):
        self.get_all_registers()
        
        for key in self.glob_param_dict:
            bitstring = self.read_register_bitstring(self.glob_base_addr, self.glob_param_dict, key)
            self.glob_param_values[key] = bitstring
        
        for pll in range(self.n_pll):
            for key in self.pll_param_dict:
                bitstring = self.read_register_bitstring(self.pll_base_addr[pll], self.pll_param_dict, key)
                self.pll_param_values[pll][key] = bitstring

    def set_all_parameters(self):
        self.get_all_registers()
        
        for key in self.glob_param_dict:
            bitstring = self.write_register_bitstring(self.glob_base_addr, self.glob_param_dict, key, self.glob_param_values)
        
        for pll in range(self.n_pll):
            for key in self.pll_param_dict:
                bitstring = self.write_register_bitstring(self.pll_base_addr[pll], self.pll_param_dict, key, self.pll_param_values[pll])

    def read_parameter_user(self, param, pll=0):
        #global parameters
        if param in ['output_1', 'output_2']:
            return self.output_options_inv[self.glob_param_values[param]]
            
        if param in ['ext_pins_p', 'ext_pins_n']:
            return str(self.__class__.unsigned_bitstring_to_int(self.glob_param_values[param]))
            
        #pll parameters
        if param in ['2nd_harm', 'pid_en']:
            return self.pll_param_values[pll][param]
            
        if param == 'a':
            w_a = self.__class__.signed_bitstring_to_int(self.pll_param_values[pll]['w_a'])
            w_b = self.__class__.signed_bitstring_to_int(self.pll_param_values[pll]['w_b'])
            return str(np.sqrt(float(w_a ** 2 + w_b ** 2)))
            
        if param == 'phi':
            w_a = self.__class__.signed_bitstring_to_int(self.pll_param_values[pll]['w_a'])
            w_b = self.__class__.signed_bitstring_to_int(self.pll_param_values[pll]['w_b'])
            return str(np.arctan2(w_a, w_b) / (2 * np.pi) * 360)
            
        if param in ['kp', 'ki']:
            return str(self.__class__.signed_bitstring_to_int(self.pll_param_values[pll][param])/ (2 ** 16))
            
        if param in ['f0', 'bw']:
            val = self.__class__.signed_bitstring_to_int(self.pll_param_values[pll][param])/ (2 ** 32) * 31.25e6
            return str(val / (int(self.pll_param_values[pll]['2nd_harm']) + 1))
        
        if param == 'alpha':
            return str(self.__class__.unsigned_bitstring_to_int(self.pll_param_values[pll][param]) / (2 ** 17))
            
        if param == 'order':
            return str(self.__class__.unsigned_bitstring_to_int(self.pll_param_values[pll][param]) + 1)
         
    def text_to_float(self, val):
        factor = 1
        if val[-1] == 'k':
            factor = 1e3
            val = val[:-1]
        elif val[-1] == 'M':
            factor = 1e6
            val = val[:-1]
        return float(val) * factor
    
    def update_parameter_user(self, param, val, pll=0):
        #global parameters
        key = param
        base_addr = self.glob_base_addr
        param_dict = self.glob_param_dict
        value_dict = self.glob_param_values
        
        if param in ['output_1', 'output_2']:
            value_bitstring = self.output_options[val]
        
        elif param in ['ext_pins_p', 'ext_pins_n']:
            n = param_dict[key][1] - param_dict[key][2] + 1
            value_bitstring = self.__class__.unsigned_int_to_bitstring(self.text_to_float(val), n)
        
        else:
            #pll parameters
            key = param
            base_addr = self.pll_base_addr[pll]
            param_dict = self.pll_param_dict
            value_dict = self.pll_param_values[pll]
            if param in ['2nd_harm', 'pid_en']:
                value_bitstring = val
                
            if param in ['a', 'phi']:
                w_a = self.__class__.signed_bitstring_to_int(value_dict['w_a'])
                w_b = self.__class__.signed_bitstring_to_int(value_dict['w_b'])
                phi = np.arctan2(w_a, w_b)
                a = np.sqrt(float(w_a ** 2 + w_b ** 2))
                if param == 'phi':
                    phi = self.text_to_float(val)/ 360 * 2 * np.pi
                if param == 'a':
                    a = self.text_to_float(val)
                n = param_dict['w_a'][1] - param_dict['w_a'][2] + 1
                w_a_bitstring =  self.__class__.signed_int_to_bitstring(float(a) * np.sin(phi), n)
                w_b_bitstring =  self.__class__.signed_int_to_bitstring(float(a) * np.cos(phi), n)
                
            if param in ['kp', 'ki']:
                n = param_dict[key][1] - param_dict[key][2] + 1
                value_bitstring = self.__class__.signed_int_to_bitstring(self.text_to_float(val) * 2**16, n)
                
            if param in ['f0', 'bw']:
                val = self.text_to_float(val)/31.25e6 * 2**32
                val = val * (int(value_dict['2nd_harm']) + 1)
                n = param_dict[key][1] - param_dict[key][2] + 1
                print(val)
                value_bitstring = self.__class__.signed_int_to_bitstring(val, n)
            
            if param == 'alpha':
                val = self.text_to_float(val)
                if val >= 1:
                    val = 0.99999999999999
                value_bitstring = '{0:017b}'.format(int(val * 2 ** 17))
                
            if param == 'order':
                val = int(val)
                if val <=1:
                    val = 1
                if val >=8:
                    val = 8
                value_bitstring = '{0:03b}'.format(int(val-1))
            
            
            
        if param in ['a', 'phi']: # these are special, because two values change
            value_dict['w_a'] = w_a_bitstring
            value_dict['w_b'] = w_b_bitstring
            self.write_register_bitstring(base_addr, param_dict, 'w_a', value_dict)
            self.write_register_bitstring(base_addr, param_dict, 'w_b', value_dict)
            self.set_register(self.get_addr(base_addr, param_dict, 'w_a'))
        else:
            value_dict[key] = value_bitstring
            self.write_register_bitstring(base_addr, param_dict, key, value_dict)
            self.set_register(self.get_addr(base_addr, param_dict, key))
            

    @staticmethod
    def signed_bitstring_to_int(bitstring):
        N = len(bitstring)
        val = RedPitaya.unsigned_bitstring_to_int(bitstring)
        if val > 2**(N-1)-1:
            return (2**N - val) * (-1)
        return val
        
    @staticmethod
    def unsigned_bitstring_to_int(bitstring):
        return int(bitstring,2)
        
    @staticmethod
    def unsigned_int_to_bitstring(val, n):
        val = int(val)
        if val<0:
            val = 0
        elif val >2**n-1:
            val = 2**n-1
        formatstr = '{:0' + str(n) + 'b}'
        return formatstr.format(val)
        
    @staticmethod
    def signed_int_to_bitstring(val, n):
        val = int(val)
        if val<-2**(n-1):
            val = -2**(n-1)
        elif val > 2**(n-1)-1:
            val = 2**(n-1)-1
        if val<0:
            val = 2**n + val
        return RedPitaya.unsigned_int_to_bitstring(val, n)
        
    @staticmethod
    def hex_to_binary_string(hex_str):
        return bin(int(hex_str.split(b'x')[1], 16))[2:].zfill(32)




        




if __name__ == '__main__':
    hostname = input("Enter hostname: ")
    n_pll = int(input("Enter number of PLLs: "))

    rp = RedPitaya(hostname, n_pll=n_pll)
    

    rp.setup_parameters()


    rp.update_parameters()

    