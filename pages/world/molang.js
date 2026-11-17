/* Safe zero-eval recursive-descent AST compiler for Bedrock / YSM Molang subset. */
const DEG_TO_RAD = Math.PI / 180;
const RAD_TO_DEG = 180 / Math.PI;
const MAX_SOURCE_LEN = 1024;
const MAX_AST_NODES = 192;

const MATH_CONSTS = {
  pi: Math.PI,
  e: Math.E,
};

const MATH_FUNCS = {
  sin: args => Math.sin((args[0] || 0) * DEG_TO_RAD),
  cos: args => Math.cos((args[0] || 0) * DEG_TO_RAD),
  tan: args => Math.tan((args[0] || 0) * DEG_TO_RAD),
  asin: args => Math.asin(Math.max(-1, Math.min(1, args[0] || 0))) * RAD_TO_DEG,
  acos: args => Math.acos(Math.max(-1, Math.min(1, args[0] || 0))) * RAD_TO_DEG,
  atan: args => Math.atan(args[0] || 0) * RAD_TO_DEG,
  atan2: args => Math.atan2(args[0] || 0, args[1] || 0) * RAD_TO_DEG,
  abs: args => Math.abs(args[0] || 0),
  sqrt: args => (args[0] > 0 ? Math.sqrt(args[0]) : 0),
  floor: args => Math.floor(args[0] || 0),
  ceil: args => Math.ceil(args[0] || 0),
  round: args => Math.round(args[0] || 0),
  trunc: args => Math.trunc(args[0] || 0),
  exp: args => Math.exp(Math.max(-40, Math.min(40, args[0] || 0))),
  ln: args => (args[0] > 0 ? Math.log(args[0]) : 0),
  min: args => Math.min(args[0] || 0, args[1] ?? 0),
  max: args => Math.max(args[0] || 0, args[1] ?? 0),
  pow: args => {
    const v = Math.pow(args[0] || 0, args[1] ?? 1);
    return Number.isFinite(v) ? v : 0;
  },
  mod: args => {
    const b = args[1] || 0;
    if (b === 0) return 0;
    const a = args[0] || 0;
    return ((a % b) + b) % b;
  },
  clamp: args => {
    const v = args[0] || 0;
    const lo = Math.min(args[1] ?? 0, args[2] ?? 0);
    const hi = Math.max(args[1] ?? 0, args[2] ?? 0);
    return Math.min(Math.max(v, lo), hi);
  },
  lerp: args => {
    const a = args[0] || 0;
    const b = args[1] || 0;
    const t = args[2] || 0;
    return a + (b - a) * t;
  },
  hermite_blend: args => {
    const t = Math.max(0, Math.min(1, args[0] || 0));
    return 3 * t * t - 2 * t * t * t;
  },
  die_roll: args => {
    const num = Math.max(0, Math.min(16, Math.floor(args[0] || 0)));
    const low = args[1] || 0;
    const high = args[2] || 0;
    return num * ((low + high) * 0.5);
  },
};

function sanitizeNumber(v) {
  return Number.isFinite(v) ? v : 0;
}

function tokenize(input) {
  const tokens = [];
  let i = 0;
  const n = input.length;
  while (i < n) {
    const ch = input[i];
    if (ch === ' ' || ch === '\t' || ch === '\r' || ch === '\n') {
      i++;
      continue;
    }
    if ((ch >= '0' && ch <= '9') || (ch === '.' && input[i + 1] >= '0' && input[i + 1] <= '9')) {
      let start = i;
      while (i < n && input[i] >= '0' && input[i] <= '9') i++;
      if (i < n && input[i] === '.') {
        i++;
        while (i < n && input[i] >= '0' && input[i] <= '9') i++;
      }
      if (i < n && (input[i] === 'e' || input[i] === 'E')) {
        i++;
        if (i < n && (input[i] === '+' || input[i] === '-')) i++;
        const expStart = i;
        while (i < n && input[i] >= '0' && input[i] <= '9') i++;
        if (i === expStart) return null;
      }
      if (i < n && (input[i] === 'f' || input[i] === 'F' || input[i] === 'd' || input[i] === 'D')) {
        i++;
      }
      const num = Number(input.slice(start, input[i - 1] >= 'A' ? i - 1 : i));
      if (!Number.isFinite(num)) return null;
      tokens.push({type: 'num', value: num});
      continue;
    }
    if ((ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') || ch === '_') {
      let start = i;
      while (i < n) {
        const c = input[i];
        if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c === '_' || c === '.') {
          i++;
        } else {
          break;
        }
      }
      const ident = input.slice(start, i).toLowerCase();
      if (ident === 'true') tokens.push({type: 'num', value: 1});
      else if (ident === 'false') tokens.push({type: 'num', value: 0});
      else if (ident === 'return') tokens.push({type: 'return'});
      else tokens.push({type: 'id', value: ident});
      continue;
    }
    const two = input.slice(i, i + 2);
    if (two === '&&' || two === '||' || two === '==' || two === '!=' || two === '<=' || two === '>=' || two === '??') {
      tokens.push({type: 'op', value: two});
      i += 2;
      continue;
    }
    if ('+-*/%<>!?:(),;='.includes(ch)) {
      tokens.push({type: 'op', value: ch});
      i++;
      continue;
    }
    return null;
  }
  tokens.push({type: 'eof', value: ''});
  return tokens;
}

export function compileMolang(source) {
  if (typeof source === 'number') {
    if (!Number.isFinite(source)) return null;
    return {constant: true, value: source, eval: () => source};
  }
  if (typeof source !== 'string') return null;
  const trimmed = source.trim();
  if (!trimmed || trimmed.length > MAX_SOURCE_LEN) return null;
  if (/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(trimmed)) {
    const val = Number(trimmed);
    if (!Number.isFinite(val)) return null;
    return {constant: true, value: val, eval: () => val};
  }

  const tokens = tokenize(trimmed);
  if (!tokens) return null;

  let pos = 0;
  let nodes = 0;
  let dynamic = false;

  const peek = () => tokens[pos];
  const next = () => tokens[pos++];
  const bumpNode = () => {
    nodes++;
    if (nodes > MAX_AST_NODES) throw new Error('Molang AST limit exceeded');
  };
  const matchOp = op => {
    if (peek().type === 'op' && peek().value === op) {
      pos++;
      return true;
    }
    return false;
  };

  function parseProgram() {
    const statements = [];
    while (peek().type !== 'eof') {
      while (matchOp(';')) { /* skip empty statements */ }
      if (peek().type === 'eof') break;
      if (peek().type === 'return') {
        next();
        statements.push(parseExpr());
        while (matchOp(';')) { /* trailing semicolons */ }
        break;
      }
      if (
        peek().type === 'id' &&
        (peek().value.startsWith('v.') || peek().value.startsWith('variable.') ||
         peek().value.startsWith('t.') || peek().value.startsWith('temp.')) &&
        tokens[pos + 1]?.type === 'op' &&
        tokens[pos + 1]?.value === '='
      ) {
        const rawVar = next().value;
        next(); // '='
        const key = rawVar.slice(rawVar.indexOf('.') + 1);
        if (!key || key === '__proto__' || key === 'constructor' || key === 'prototype') {
          throw new Error('Disallowed variable name');
        }
        const rhs = parseExpr();
        dynamic = true;
        bumpNode();
        statements.push({kind: 'assign', key, rhs});
      } else {
        statements.push(parseExpr());
      }
      if (!matchOp(';') && peek().type !== 'eof') {
        throw new Error('Unexpected token');
      }
    }
    if (!statements.length) throw new Error('Empty Molang expression');
    return statements;
  }

  function parseExpr() {
    let node = parseNullish();
    if (matchOp('?')) {
      bumpNode();
      const whenTrue = parseExpr();
      const whenFalse = matchOp(':') ? parseExpr() : {kind: 'num', value: 0};
      return {kind: 'ternary', cond: node, whenTrue, whenFalse};
    }
    return node;
  }

  function parseNullish() {
    let left = parseOr();
    while (matchOp('??')) {
      bumpNode();
      const right = parseOr();
      left = {kind: 'bin', op: '??', left, right};
    }
    return left;
  }

  function parseOr() {
    let left = parseAnd();
    while (matchOp('||')) {
      bumpNode();
      const right = parseAnd();
      left = {kind: 'bin', op: '||', left, right};
    }
    return left;
  }

  function parseAnd() {
    let left = parseEquality();
    while (matchOp('&&')) {
      bumpNode();
      const right = parseEquality();
      left = {kind: 'bin', op: '&&', left, right};
    }
    return left;
  }

  function parseEquality() {
    let left = parseComparison();
    while (peek().type === 'op' && (peek().value === '==' || peek().value === '!=')) {
      bumpNode();
      const op = next().value;
      const right = parseComparison();
      left = {kind: 'bin', op, left, right};
    }
    return left;
  }

  function parseComparison() {
    let left = parseAdditive();
    while (peek().type === 'op' && (peek().value === '<' || peek().value === '<=' || peek().value === '>' || peek().value === '>=')) {
      bumpNode();
      const op = next().value;
      const right = parseAdditive();
      left = {kind: 'bin', op, left, right};
    }
    return left;
  }

  function parseAdditive() {
    let left = parseMultiplicative();
    while (peek().type === 'op' && (peek().value === '+' || peek().value === '-')) {
      bumpNode();
      const op = next().value;
      const right = parseMultiplicative();
      left = {kind: 'bin', op, left, right};
    }
    return left;
  }

  function parseMultiplicative() {
    let left = parseUnary();
    while (peek().type === 'op' && (peek().value === '*' || peek().value === '/' || peek().value === '%')) {
      bumpNode();
      const op = next().value;
      const right = parseUnary();
      left = {kind: 'bin', op, left, right};
    }
    return left;
  }

  function parseUnary() {
    if (peek().type === 'op' && (peek().value === '-' || peek().value === '+' || peek().value === '!')) {
      bumpNode();
      const op = next().value;
      const arg = parseUnary();
      return {kind: 'unary', op, arg};
    }
    return parsePrimary();
  }

  function parsePrimary() {
    bumpNode();
    const tok = peek();
    if (tok.type === 'num') {
      next();
      return {kind: 'num', value: tok.value};
    }
    if (matchOp('(')) {
      const inner = parseExpr();
      if (!matchOp(')')) throw new Error('Unclosed parenthesis');
      return inner;
    }
    if (tok.type === 'id') {
      next();
      const id = tok.value;
      if (id.startsWith('math.')) {
        const fnName = id.slice(5);
        if (Object.prototype.hasOwnProperty.call(MATH_CONSTS, fnName)) {
          if (matchOp('(') && !matchOp(')')) throw new Error('Math constant takes no args');
          return {kind: 'num', value: MATH_CONSTS[fnName]};
        }
        const fn = Object.prototype.hasOwnProperty.call(MATH_FUNCS, fnName) ? MATH_FUNCS[fnName] : null;
        if (!fn) throw new Error('Unsupported math function: ' + fnName);
        if (!matchOp('(')) throw new Error('Expected call parentheses');
        const args = [];
        if (!matchOp(')')) {
          do {
            args.push(parseExpr());
            if (args.length > 4) throw new Error('Too many math arguments');
          } while (matchOp(','));
          if (!matchOp(')')) throw new Error('Unclosed call parentheses');
        }
        return {kind: 'math', fn, args};
      }
      if (id.startsWith('q.') || id.startsWith('query.')) {
        const key = id.slice(id.indexOf('.') + 1);
        if (!key) throw new Error('Empty query key');
        if (matchOp('(')) {
          // Allow zero-arg or 1-arg query calls by consuming args safely
          if (!matchOp(')')) {
            do { parseExpr(); } while (matchOp(','));
            if (!matchOp(')')) throw new Error('Unclosed query call');
          }
        }
        dynamic = true;
        return {kind: 'query', key};
      }
      if (id.startsWith('v.') || id.startsWith('variable.') || id.startsWith('t.') || id.startsWith('temp.')) {
        const key = id.slice(id.indexOf('.') + 1);
        if (!key) throw new Error('Empty variable key');
        dynamic = true;
        return {kind: 'var', key};
      }
      throw new Error('Unknown identifier: ' + id);
    }
    throw new Error('Unexpected token in primary');
  }

  let statements;
  try {
    statements = parseProgram();
    if (peek().type !== 'eof') return null;
  } catch {
    return null;
  }

  function evalNode(node, ctx, vars) {
    switch (node.kind) {
      case 'num':
        return node.value;
      case 'query': {
        const raw = ctx && Object.prototype.hasOwnProperty.call(ctx, node.key) ? ctx[node.key] : 0;
        return typeof raw === 'boolean' ? (raw ? 1 : 0) : sanitizeNumber(Number(raw));
      }
      case 'var':
        return vars && Object.prototype.hasOwnProperty.call(vars, node.key) ? sanitizeNumber(vars[node.key]) : 0;
      case 'assign': {
        const v = sanitizeNumber(evalNode(node.rhs, ctx, vars));
        if (vars) vars[node.key] = v;
        return v;
      }
      case 'unary': {
        const v = evalNode(node.arg, ctx, vars);
        if (node.op === '-') return -v;
        if (node.op === '+') return v;
        return v === 0 ? 1 : 0;
      }
      case 'bin': {
        if (node.op === '&&') return evalNode(node.left, ctx, vars) !== 0 && evalNode(node.right, ctx, vars) !== 0 ? 1 : 0;
        if (node.op === '||') return evalNode(node.left, ctx, vars) !== 0 || evalNode(node.right, ctx, vars) !== 0 ? 1 : 0;
        const l = evalNode(node.left, ctx, vars);
        const r = evalNode(node.right, ctx, vars);
        switch (node.op) {
          case '+': return sanitizeNumber(l + r);
          case '-': return sanitizeNumber(l - r);
          case '*': return sanitizeNumber(l * r);
          case '/': return r === 0 ? 0 : sanitizeNumber(l / r);
          case '%': return r === 0 ? 0 : sanitizeNumber(l % r);
          case '<': return l < r ? 1 : 0;
          case '<=': return l <= r ? 1 : 0;
          case '>': return l > r ? 1 : 0;
          case '>=': return l >= r ? 1 : 0;
          case '==': return Math.abs(l - r) < 1e-7 ? 1 : 0;
          case '!=': return Math.abs(l - r) >= 1e-7 ? 1 : 0;
          case '??': return l;
          default: return 0;
        }
      }
      case 'ternary':
        return evalNode(node.cond, ctx, vars) !== 0
          ? evalNode(node.whenTrue, ctx, vars)
          : evalNode(node.whenFalse, ctx, vars);
      case 'math': {
        const evaluated = new Array(node.args.length);
        for (let i = 0; i < node.args.length; i++) evaluated[i] = evalNode(node.args[i], ctx, vars);
        return sanitizeNumber(node.fn(evaluated));
      }
      default:
        return 0;
    }
  }

  const run = (ctx = {}) => {
    const vars = ctx?.vars || Object.create(null);
    let last = 0;
    for (let i = 0; i < statements.length; i++) {
      last = evalNode(statements[i], ctx, vars);
    }
    return sanitizeNumber(last);
  };

  if (!dynamic) {
    const constValue = run({});
    return {constant: true, value: constValue, eval: () => constValue};
  }
  return {constant: false, value: null, eval: run};
}

export function compileMolangVector(value) {
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return null;
    const vec = [value, value, value];
    return {dynamic: false, constant: vec, eval: () => vec};
  }
  if (typeof value === 'string') {
    const fn = compileMolang(value);
    if (!fn) return null;
    if (fn.constant) {
      const vec = [fn.value, fn.value, fn.value];
      return {dynamic: false, constant: vec, eval: () => vec};
    }
    return {
      dynamic: true,
      constant: null,
      eval: ctx => {
        const v = fn.eval(ctx);
        return [v, v, v];
      },
    };
  }
  if (Array.isArray(value)) {
    if (value.length === 1) return compileMolangVector(value[0]);
    if (value.length !== 3) return null;
    const parts = value.map(compileMolang);
    if (parts.some(p => !p)) return null;
    if (parts.every(p => p.constant)) {
      const vec = [parts[0].value, parts[1].value, parts[2].value];
      return {dynamic: false, constant: vec, eval: () => vec};
    }
    return {
      dynamic: true,
      constant: null,
      eval: ctx => [parts[0].eval(ctx), parts[1].eval(ctx), parts[2].eval(ctx)],
    };
  }
  return null;
}
