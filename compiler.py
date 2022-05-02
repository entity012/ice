# TODO: Remove varinfo(). Make methods under the Variable class.

# Flags for varinfo()
[USE_UNITSIZE, GET_CLAUSE, GET_LENGTH, GET_SIZE, GET_NBYTES, GET_REG,
	*_] = (1<<i for i in range(8))

# String States
CHAR, ESCAPE, HEX_ESCAPE, *_ = range(8)

from sys import argv
debug = False
if '-d' in argv: debug = True; argv.remove('-d')
if len(argv) <2:
	if debug: argv.append('Examples\\hello.ice')
	else: print('Input file not specified'); quit(1)
name = argv[1].rpartition('.')[0]
if len(argv)<3: argv.append(name+'.asm')

infile = open(argv[1])
out = open(argv[2], 'w')
def output(*args, file = out, **kwargs): print(*args, **kwargs, file = file)

sfile = open('builtins.ice-snippet')

# byte if size <= 8, word if 16 ...
size_list = ['byte', 'byte', 'byte', 'byte', 'word', 'dword', 'qword']
reg_list  = [' l', ' l', ' l', ' l', ' x', 'ex', 'rx']

escape_sequences = {
	'a':'\a','n':'\n','f':'\f','t':'\t','v':'\v','r':'\r',
	"'":'\'','"':'"','\\':'\\'}

# a few dunder methods
unary = {
	'+': '__pos__',
	'-': '__neg__',
	'~': '__invert__',
	'*': '__deref__',
	'&': '__ref__',
}

binary = {
	'|' : '__or__',
	'&' : '__and__',
	'^' : '__xor__',
	'+' : '__add__',
	'-' : '__sub__',
	'*' : '__mul__',
	'/' : '__truediv__',
	# '//': '__floordiv__',
	# '**': '__pow__',
	# '<<': '__lshift__',
	# '>>': '__rshift__',
}


import re
class Patterns:
	wsep  = re.compile(r'\b')
	hex   = re.compile(r'[\da-fA-F]')
	equal = re.compile(r'(?<!=)=(?!=)')
	space = re.compile(r'\s+')
	empty = re.compile(r'\[\][3-6]')

	shape = r'(?:(?:\[\d+\])*|\[\]|\*)'
	unit  = r'(?:[3-6]|[A-Za-z_]\w*)' # add tuple support
	label = rf'{shape}{unit}'
	token = re.compile(rf'@({label})|\d+|[a-zA-Z_]\w*|(\S)')
	decl  = re.compile(rf'@({label}\s+|{shape}[3-6])([A-Za-z_]\w*)')
	dest  = re.compile(rf'(@{label}\s+|{shape}[3-6])?([A-Za-z_]\w*)'
			r'(?:\[([A-Za-z_]\w*)\])?')

	stmt  = re.compile(r'(([\'"])(\\?.)*?\2|[^#])*')
	sub   = re.compile(r'(?i)%(\d+)([a-z])?\b')

class Variable:
	def __init__(self, label, name):
		self.name = name
		self.init = None
		self.enc_name = self.var_encode()
		self.size = label_size(label)
		self.labels = [label]

	def __repr__(self):
		return f'{type(self).__name__}(@{self.get_label()} {self.name}, '\
			f'size = {self.size})'

	def var_encode(self):
		enc_name = self.name.replace('_', '__')
		return '$'+enc_name

	def get_label(self):
		return self.labels[-1]

	def get_clause(self, unit = False):
		label = self.get_label()
		size = int(label[-1]) if '*' not in label or unit else 6
		return f'{size_list[self.size]} [{self.enc_name}]'

class Register(Variable):
	def var_encode(self):
		# assuming label[0] for register gives unit
		unit = self.get_label()[0]
		if unit == '*': unit = '6' # 64-bit
		a, b = reg_list[int(unit)]
		return a+self.name+b

	def get_clause(self, unit = False): return self.var_encode()

class Literal(Variable):
	def var_encode(self): return self.name
	def get_clause(self, unit = False): return self.name

def err(msg):
	print(f'File "{argv[1]}", line {line_no}')
	print('   ', line.strip())
	if debug: raise RuntimeError(repr(msg)) # temporary, for debugging

	print(msg)
	quit(1)

def get_length(label):
	# if label[0] == '*': return 1
	length = 1
	# add support for dynamic arrays
	for i in label[1:-2].split(']['):
		if not i: continue
		length *= int(i)
	return length

def label_size(label): # number of bytes
	fac = 1
	num = ''
	for i, d in enumerate(label):
		if d.isalpha(): num = labels[label[i:]].size; break
		if d == '*': num = 6; break
		# add support for varrs (6, *d)
		if d == ']': fac *= int(num); num = ''
		elif d.isdigit(): num += d
	if num: return (fac<<(max(0, int(num)-3)))
	# control comes here only if the label format isn't right
	err('SyntaxError: Invalid label syntax.')

def element_size(label):
	if '*' in label: num = 8
	elif label[-1].isdigit(): num = int(label[-1])
	else: num = 8

	# TODO: support named labels

	return num

def varinfo(var, flags = GET_CLAUSE, reg = 'a'):
	if var.isdigit(): var = Literal('6', var)
	# varinfo doesn't support registers
	elif var in variables: var = variables[var]
	else: err(f'ValueError: {var!r} is not declared.')

	# size, int and reg for pointers will already be known, so it isn't needed
	# clause of a pointer has to be with a dword, so no need extra flag
	# no, but it doesn't work with the builtins so yes extra flag
	label = var.get_label()
	# add support for size from label names
	size = int(label[-1]) if '*' not in label or flags&USE_UNITSIZE else 6
	out = ()
	if flags&GET_CLAUSE: out += (var.get_clause(flags&USE_UNITSIZE),)
	if flags&GET_LENGTH: out += (get_length(var.get_label()),)
	if flags&GET_SIZE: out += (f'{size_list[size]}',)
	if flags&GET_NBYTES: out += (var.size,)
	if flags&GET_REG: a, b = reg_list[size]; out += (a+reg+b,)

	if len(out) == 1: return out[0]
	return out

def fun_encode(label, op):
	# check if label has that method?
	op = op.replace('_', '__')
	if len(op.lstrip('_'))+4 <= len(op) >= len(op.rstrip('_'))+4:
		op = '_d'+op[4:-4]
	else: op = '_m'+op

	# # _a and _u need to be preserved
	# if label[0] == '_' and label[1] != '_': label = label.replace('_', ' ', 1)
	enc_op = label.translate({
		# ord(' '): '_',
		ord('_'): '__',
		ord('*'): '_s',
		ord('['): '_a',
		ord(']'): '_',
	})

	enc_op = label+op
	return enc_op

def new_var(token, init = None):
	match = Patterns.decl.match(token)
	label, name = match[1].strip(), match[2]

	if Patterns.empty.fullmatch(label):
		if init is None:
			err('SyntaxError: Implicit length requires initialisation.')
		init_length = len(init)//element_size(label)
		label = label[0]+str(init_length)+label[1:]

	if name in variables: # check prev
		var = variables[name]
		size = label_size(label)
		if var.size != size: err(f'TypeError: {var.name!r}'
			f'uses {var.size} bytes, but {label!r} needs {size} bytes.')
		if init:
			if var.init and var.init != init:
				err(f'ValueError: Initialisation mismatch for {var.name!r}.'
					f'\n  Expected {[*var.init]}'
					f'\n  Got      {[*init]}')
			var.init = init
		return

	var = Variable(label, name)

	variables[name] = var

	if not init: output(var.enc_name+': resb', var.size)
	else: # check if init matches label
		if '[' not in label:
			err('ValueError: Cannot initialize non-sequence as sequence.')
		if '*' in label: err('ValueError: Sequence initialisation '
			'not yet supported for pointers.')
		size = label_size(label)
		if len(init) != size:
			err(f'TypeError: {var.name!r} needs {size} bytes. '
				f'Got {len(init)} instead.')
		var.init = init

def get_call_label(enc_op):
	if enc_op in snippets: return snippets[enc_op][1]
	return functions[enc_op][0] # (ret_label, *arg_sizes)

def insert_snippet(fun, args = (), encode = True):
	sfile.seek(snippets[fun][0])
	for line in sfile:
		if line in (';', ';\n'): break

		offset = 0
		for match in Patterns.sub.finditer(line):
			start, end = match.span()
			start += offset
			end   += offset
			arg = args[int(match[1])]
			tail = match[2]

			if not encode: sub = arg
			elif not tail: sub = varinfo(arg)
			elif tail == 'r': sub = variables[arg].enc_name
			elif tail == 's': sub = varinfo(arg, flags = GET_SIZE)
			elif tail == 'n': sub = str(varinfo(arg, flags = GET_NBYTES))
			elif tail == 'l': sub = str(varinfo(arg, flags = GET_LENGTH))
			elif tail in 'abcd': sub = varinfo(arg, flags = GET_REG, reg = tail)
			else: continue

			offset += len(sub)-len(match[0])
			line = line[:start]+sub+line[end:]
		output(line.strip())

# def call_function(subject, op, args = (), label = None):
	# if label is not None: enc_op = fun_encode(label, op); args = (subject,)+args
	# elif subject in variables:
	# 	label = variables[subject].get_label()
	# 	enc_op = fun_encode(label, op)
	# elif op == '__call__': enc_op = subject.replace('_', '__')
	# else: err(f'NameError: Variable {subject!r} not declared.')

# Would take subject to check if it is a call to a function
# and not to a variable with a __call__ method.
# Should that check be here?
def call_function(enc_op, args = (), reg_sizes = ()):
	if enc_op in snippets:
		insert_snippet(enc_op, args = args)
		return

	if enc_op not in functions: err('Function not defined.')

	# Make this compatible with 64-bit
	offset = 0
	for i, arg in enumerate(args):
		if i < len(reg_sizes):
			arg_clause, size = varinfo(arg), reg_sizes[i]
		else:
			arg_clause, size = varinfo(arg, flags = GET_CLAUSE|GET_NBYTES)
		output('push', arg_clause)
		offset += size

	# if op != '__call__':
	# 	subject_clause, size = varinfo(subject, flags = GET_CLAUSE|GET_NBYTES)
	# 	output('push', subject_clause)
	# 	offset += size
	# 	output('call', enc_op)
	# else: output('call', subject)

	output('call', enc_op)
	output('add esp,', offset)

def assign(dest, imm = None):
	match = Patterns.dest.match(dest)
	var, index = match[2], match[3]
	# print(dest, (var, index), sep = ' -> ')

	if index:
		if imm: output('mov eax,', imm)
		fun = fun_encode(var.get_label(), '__setitem__')
		call_function(fun, (var, index))
		return

	if variables[var].shape[0] == '*':
		if not imm: output('mov ebx, eax'); src = 'ebx'
		else: src = imm
		insert_snippet('_ptralloc', (var, src), encode = False)
		return

	if imm: output(f'mov {varinfo(var)}, {imm}')
	else:
		clause, reg = varinfo(var, flags = GET_CLAUSE|GET_REG)
		output(f'mov {clause}, {reg}')

variables = {}
functions = {}
labels    = {}

snippets = {}
tell = 0
for line_no, line in enumerate(sfile, 1):
	tell += len(line)
	if not line.startswith('; '): continue
	name, ret, *args = line[2:].split()
	snippets[name] = (name, ret, args)
# starts at a line starting with '; ' (mind the space)
# ends at a line with just ';' (refer `insert_snippet()`)

if debug: print('BUILTINS: ', *snippets)

insert_snippet('_header')

# Writing to bss segment

output('\nsegment .bss')
for line_no, line in enumerate(infile, 1):
	stmt = Patterns.stmt.match(line)[0].strip()
	lhs, *rhs = Patterns.equal.split(stmt, maxsplit = 1)
	lhs = lhs.strip()
	decls = lhs.split()
	decl = Patterns.decl.match(lhs)

	if not decl: continue

	if not rhs:
		for decl in decls:
			decl = decl.strip()
			if Patterns.decl.match(decl): new_var(decl)
			else: err(f'SyntaxError: Expected a declaration token.')
		continue

	if not lhs: err('SyntaxError: Assignment without destination.')
	if len(decls) > 1:
		err('SyntaxError: Assignment with multiple declarations')
	var = decl[0]
	init = bytearray()
	size = element_size(decl[1])

	rhs = rhs[0].strip()
	end = False
	# Clean this up. Must expect comma after each value.
	if rhs[0] == '[':
		for token in Patterns.wsep.split(rhs[1:]):
			token = token.strip()
			if not token: continue
			if end:
				err('SyntaxError: Token found after array initialisation.')
			if token.isdigit(): init.extend(int(token).to_bytes(size, 'big'))
			elif token == ']': end = True
			elif token != ',': err('SyntaxError: Invalid token'
				f' {token!r} in array initialisation.')
		if not end: err('SyntaxError: Multi-line arrays are not yet supported.')

	elif rhs[0] in '"\'':
		s = rhs[0]
		str_state = CHAR
		for c in rhs[1:]:
			if end: err('SyntaxError: Token found after string initialisation.')
			elif str_state == ESCAPE:
				str_state = CHAR
				if c == 'x': str_state = HEX_ESCAPE; init.append(0)
				elif c not in escape_sequences:
					err(f'SyntaxError: Invalid escape character {c!r}.')
				else: init.append(ord(escape_sequences[c]))
			elif str_state == HEX_ESCAPE:
				if not Patterns.hex.match(c):
					err('SyntaxError: Expected hexadecimal character.')

				if not init[-1]: init[-1] |= int(c, 16)<<4 | 15
				else:
					init[-1] = ~15&init[-1] | int(c, 16)
					str_state = 0

			elif c == '\\': str_state = ESCAPE
			elif c == s: end = True
			else: init.append(ord(c))
		else:
			if not end: err('SyntaxError: EOL while parsing string.')
	new_var(var, init = init)

# Writing to the data segment

if debug: print('VARIABLES:', *variables.values())

output()
insert_snippet('_data')
if debug: print('\nINITS:')
inits = False
for var in variables.values():
	if not var.init: continue
	inits = True

	if debug: print(var.name, '=', var.init)
	output(var.enc_name+': db', end = ' ')
	if not var.init.isascii(): output(*var.init, sep = ', ')
	else: output(f'`{repr(var.init)[12:-2].replace('`', '\\`')}`')
if debug and not inits: print(None)

# Writing to the text segment

infile.seek(0)
output('\nsegment .text')
output('_main:')
for line_no, line in enumerate(infile, 1):
	line = Patterns.stmt.match(line)[0]
	dest, _, exp = line.rpartition('=')
	dest = dest.strip()
	exp  = exp.strip()

	if not dest and Patterns.decl.match(exp): continue
	# if debug: print(f'{line_no}:', line.strip())
	isdecl = bool(Patterns.decl.match(dest))
	# decl = True
	uni_chain = []
	args = []
	cast = None
	b_label = None
	bin_op  = None  # remembered for use after unary operations

	# output(f'\n;{line_no}:', line.strip())

	# expression lexing (mostly cleaned up)
	for token in Patterns.token.finditer(exp):
		if bin_op is True: # expecting a binary operator
			if token[0] not in binary:
				err('SyntaxError: Expected binary operator.')
			bin_op = fun_encode(b_label, binary[token[0]])
			continue

		if token[2]: # Expecting unary. Got some symbol.
			if token[2] in '["\'':
				if bin_op or uni_chain: err('SyntaxError: '
					'Operations not yet supported on sequence literals.')
				if not isdecl: err('SyntaxError: Sequence literals '
					'not yet supported outside declaration.')
				dest = None; break # sequence literals initialise right now
			if token[2] not in unary:
				err('SyntaxError: Invalid unary operator.')
			uni_chain.append(token[2])
			cast = None
			continue

		if token[1]: cast = label = token[0]
		elif token[0].isdigit(): v_label = label = cast or '6'
		else: v_label = label = cast or variables[token[0]].get_label()
		assert cast or not uni_chain[-1].isidentifier()
		assert not cast or uni_chain[-1].isidentifier()
		for i, uni in enumerate(reversed(uni_chain), 1):
			if uni.isidentifier(): break
			uni_chain[-i] = fun_encode(label, unary[uni])
			label = get_call_label(uni_chain[-i])

		if token[1]: continue # label cast. Don't call the functions yet.

		# bin_op here is either a name or None, never True
		if bin_op: output('mov rcx, rax')

		var = token[0]
		if uni_chain:
			call_function(uni_chain[-1], (var,))
			size = label_size(get_call_label(uni_chain[-1]))
		elif not var.isdigit(): size = 8; output(f'mov rax, {var}')
		else:
			clause, size = varinfo(var, flags = GET_CLAUSE|GET_NBYTES)
			output(f'mov rax, {clause}')
		for uni in reversed(uni_chain[:-1]):
			if uni.isidentifier(): enc_op = uni
			else: enc_op = fun_encode(label, unary[uni])
			call_function(enc_op, ('$a',), reg_sizes = (size,))
			label = get_call_label(enc_op)
			size = label_size(label)
		# if <arg of bin_op>.size != label_size(label):
		# 	err('TypeError: Size mismatch for binary operator.')

		if bin_op:
			call_function(bin_op, ('$a', '$c'),
				reg_sizes = (size, label_size(b_label)))
			b_label = get_call_label(bin_op)
		elif uni_chain: b_label = get_call_label(uni_chain[0])
		else: b_label = v_label

		cast = None
		bin_op = True
		uni_chain = []

		# TODO:
		# 	if   token[0] == '(': op = '__call__'
		# 	elif token[0] == '[': op = '__getitem__'
		# 	elif token == '.': op = False
		# 	elif op == False: op = token

	# just assignment or no op
	# for no op (and for asignment also maybe?) check `label is None`
	if not dest:
		if subject: output(f';{line_no}: no op {subject}')
	elif not subject: err('SyntaxError: Expected an expression.')
	elif subject.isdigit():
		output(f'\n;{line_no}:', line.strip())
		assign(dest, imm = subject)
	else:
		sclause, sreg = varinfo(subject, flags = GET_CLAUSE|GET_REG)
		output(f'mov {sreg}, {sclause}')
		assign(dest)
