// Session-memory only: one explicit reading-return snapshot, never literature.
const pending=new Map();
export function rememberCanvas(scope,state){pending.clear();pending.set(scope,structuredClone(state));}
export function returnCanvas(scope,hash){const p=new URLSearchParams(hash.replace(/^#/,''));if(p.get('canvas-return')!=='1')return null;const value=pending.get(scope);pending.delete(scope);return value?.frameworkId===p.get('framework')?structuredClone(value):null;}
