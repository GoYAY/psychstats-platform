// Namespaced identities; proximity, aliases and shared citations never merge nodes.
export function refKey(ref){if(!ref||!['personal','official','pending'].includes(ref.space)||typeof ref.id!=='string'||!ref.id)throw new TypeError('Invalid graph reference');return ref.space+':'+ref.id;}
export function edgeKey(edge){const ends=[refKey(edge.from),refKey(edge.to)];if(edge.type==='contrasts')ends.sort();return edge.type+'|'+ends.join('|');}
