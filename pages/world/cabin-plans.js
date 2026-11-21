import {BED_PLACEMENTS, DESK_PLACEMENTS, furniturePoint} from './cabin-layout.js';

export const CABIN_STYLES = [
  {id:'cottage', name:'田园木屋'},
  {id:'whale_coast', name:'DeepSeek 鲸鱼娘海边小屋'},
  {id:'witch_court', name:'魔女审判小屋'},
];

export const SHELF_PLACEMENTS = {
  back_wall:[-2.52,2.48,-3.37,0], left_wall:[-4.68,2.42,.45,Math.PI/2],
  right_wall:[3.62,2.42,-.25,-Math.PI/2], near_window:[1.68,2.48,-3.37,0],
  center:[-2.52,2.48,-3.37,0],
};
const cottage = {
  id:'cottage', beds:BED_PLACEMENTS, desks:DESK_PLACEMENTS, shelves:SHELF_PLACEMENTS,
  window:[.05,2.25,-3.51,0], kitchen:[-4.55,0,2.75,0], washstand:[-4.60,0,-2.70,0],
  table:[3.33,0,1.80,0], wardrobe:[3.52,0,-2.38,0], plant:[4.07,0,2.65,0], rug:[0,.15,1.12,0],
};
const coast = {
  ...cottage, id:'whale_coast',
  beds:{...BED_PLACEMENTS,left_wall:[-3.18,0,1.10,Math.PI/2]},
  desks:{...DESK_PLACEMENTS,near_window:{desk:[.63,0,-2.30,0],chair:[.63,0,-.68,0],attach:'D'}},
  shelves:{...SHELF_PLACEMENTS,back_wall:[-2.76,2.50,-3.37,0]},
  window:[.67,2.25,-3.51,0], kitchen:[-4.55,0,-2.63,0], washstand:[-4.60,0,-.91,0],
  table:[3.46,0,2.01,-Math.PI/2], wardrobe:[3.74,0,-2.57,0], plant:[4.36,0,3.04,0], rug:[.42,.15,1.20,0],
};
const court = {
  ...cottage, id:'witch_court',
  beds:{...BED_PLACEMENTS,left_wall:[-3.22,0,.52,0]},
  desks:{...DESK_PLACEMENTS,near_window:{desk:[3.42,0,-1.57,-Math.PI/2],chair:[1.94,0,-1.57,-Math.PI/2],attach:'C1'}},
  shelves:{...SHELF_PLACEMENTS,back_wall:[1.60,2.39,-3.34,0]},
  window:[-.30,2.25,-3.51,0], wardrobe:[-2.83,0,-2.85,0],
  table:[3.38,0,1.76,Math.PI/2], plant:[4.30,0,2.85,0], rug:[.02,.15,1.00,0],
};
const plans = new Map([cottage,coast,court].map(plan=>[plan.id,plan]));
export function cabinPlan(id) {return plans.get(id) || cottage;}
export function relocatePoint(from,to,[x,y,z]) {
  const c=Math.cos(from[3]), s=Math.sin(from[3]), dx=x-from[0], dz=z-from[2];
  return furniturePoint(to,dx*c-dz*s,y-from[1],dx*s+dz*c);
}
export function placeObject(object,[x,y,z,yaw]) {
  object.position.set(x,y,z);
  object.rotation.y=yaw;
}
