#!/usr/bin/env python3

opcodes = [
    # mask, identifier, name
    (0xFC, 0x88, 'mov-reg'),
    (0xF0, 0xB0, 'mov-imm-reg'),
    (0xFC, 0x00, 'add'),
    (0xFC, 0x80, 'arith-imm'),
    (0xFE, 0x04, 'add-imm-acc'),
    (0xFC, 0x28, 'sub'),
    (0xFE, 0x2C, 'sub-imm-acc'),
    (0xFC, 0x38, 'cmp'),
    (0xFE, 0x3C, 'cmp-imm-acc'),
    (0xFF, 0x74, 'je'),
    (0xFF, 0x7C, 'jl'),
    (0xFF, 0x7E, 'jle'),
    (0xFF, 0x72, 'jb'),
    (0xFF, 0x76, 'jbe'),
    (0xFF, 0x7A, 'jp'),
    (0xFF, 0x70, 'jo'),
    (0xFF, 0x78, 'js'),
    (0xFF, 0x75, 'jne'),
    (0xFF, 0x7D, 'jnl'),
    (0xFF, 0x7F, 'jnle'),
    (0xFF, 0x73, 'jnb'),
    (0xFF, 0x77, 'jnbe'),
    (0xFF, 0x7B, 'jnp'),
    (0xFF, 0x71, 'jno'),
    (0xFF, 0x79, 'jns'),
    (0xFF, 0xE2, 'loop'),
    (0xFF, 0xE1, 'loopz'),
    (0xFF, 0xE0, 'loopnz'),
    (0xFF, 0xE3, 'jcxz'),
]

registers = [
    ['al', 'cl', 'dl', 'bl', 'ah', 'ch', 'dh', 'bh'],
    ['ax', 'cx', 'dx', 'bx', 'sp', 'bp', 'si', 'di']
]

class Decoder:
    def __init__(self, fin):
        self.fin = fin
        self.cur_byte = 0
        self.code = [] # [(code, byteidx)]
        self.labels = {} # {byteidx: label}
    def read(self):
        self.cur_byte += 1
        ret = self.fin.read(1)
        if not ret:
            return None
        return ret[0]
    def read_number(self, n=1):
        if n == 1:
            return self.read()
        elif n == 2:
            ret = self.read()
            ret += self.read() << 8
            return ret
    def add_label(self, byteidx):
        if byteidx in self.labels:
            return self.labels[byteidx]
        n = len(self.labels)+1
        l = f'label{n}'
        self.labels[byteidx] = l
        return l
    def read_address_calc(self, w, mod, rm):
        dest = ''
        if mod == 3:
            dest = registers[w][rm]
        else:
            if rm == 6 and mod == 0:
                dest = f'[{self.read_number(w+1)}]'
            else:
                calcs = ['bx + si', 'bx + di', 'bp + si', 'bp + di',
                         'si', 'di', 'bp', 'bx']
                c = calcs[rm]
                pl = 0
                if mod > 0:
                    pl = self.read_number(mod)
                if pl == 0:
                    dest = f'[{c}]'
                else:
                    dest = f'[{c} + {pl}]'
        return dest
    def decode_register_pair(self, d, w):
        byt2 = self.read()
        mod = (byt2 & 0xC0) >> 6
        reg = (byt2 & 0x38) >> 3
        rm = (byt2 & 0x07)
        src = registers[w][reg]
        dest = self.read_address_calc(w, mod, rm)
        if d:
            src, dest = dest, src
        return src, dest
    def decode_single(self, byt, name):
        if name == 'mov-reg':
            d = (byt & 2) >> 1
            w = byt & 1
            src, dest = self.decode_register_pair(d, w)
            return f'mov {dest}, {src}'
        elif name == 'mov-imm-reg':
            w = (byt & 8) >> 3
            reg = byt & 7
            dest = registers[w][reg]
            data = self.read_number(w+1)
            return f'mov {dest}, {data}'
        elif name in ['add', 'sub', 'cmp']:
            d = (byt & 2) >> 1
            w = byt & 1
            src, dest = self.decode_register_pair(d, w)
            return f'{name} {dest}, {src}'
        elif name == 'arith-imm':
            s = (byt & 2) >> 1
            w = byt & 1
            byt2 = self.read()
            mod = (byt2 & 0xC0) >> 6
            op = (byt2 & 0x38) >> 3
            ops = ['add', 'adc', 'sbb', '', '', 'sub', '', 'cmp']
            opname = ops[op]
            rm = (byt2 & 0x07)
            dest = self.read_address_calc(w, mod, rm)
            wd = ''
            n = 1
            if s == 0 and w == 1:
                n = 2
            src = self.read_number(n)
            if w == 1 and s == 1 and src & 0x80:
                src = -(((src - 0x80) - 1) ^ 0x7F)
            elif '[' in dest and src <= 0xFF:
                wd = ' byte' if w == 0 else ' word'
            return f'{opname}{wd} {dest}, {src}'
        elif name in ['add-imm-acc', 'sub-imm-acc', 'cmp-imm-acc']:
            op = name.split('-')[0]
            w = byt & 1
            dest = 'al' if w == 0 else 'ax'
            num = self.read_number(w + 1)
            return f'{op} {dest}, {num}'
        elif name[0] == 'j' or name.startswith('loop'):
            disp = self.read()
            if disp & 0x80:
                disp = -(((disp - 0x80) - 1) ^ 0x7F)
            lab = self.add_label(self.cur_byte + disp)
            return f'{name} {lab} ; {disp}'
        return name
    def decode(self):
        while True:
            pos = self.cur_byte
            byt = self.read()
            if byt == None:
                break
            for mask, ident, name in opcodes:
                if byt & mask == ident:
                    dec = self.decode_single(byt, name)
                    break
            else:
                dec = f'Unknown byte {hex(int(byt))}'
            self.code.append((dec, pos))
    def write(self, fout):
        fout.write('bits 16\n\n')
        for dec, byteidx in self.code:
            if byteidx in self.labels:
                fout.write(self.labels[byteidx] + ':\n')
            fout.write(dec + '\n')

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('infile', type=argparse.FileType('rb'))
    parser.add_argument('outfile', type=argparse.FileType('w'))
    args = parser.parse_args()
    D = Decoder(args.infile)
    D.decode()
    D.write(args.outfile)
