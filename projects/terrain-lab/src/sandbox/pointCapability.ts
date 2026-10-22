export function requireWebGl2(createCanvas: () => HTMLCanvasElement = () => document.createElement('canvas')): void {
  if (!createCanvas().getContext('webgl2'))
    throw new Error('deck.gl needs WebGL2. MapLibre point display remains available.');
}
