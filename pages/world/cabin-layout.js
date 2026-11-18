// Transforms of the rendered furniture. Pose anchors use the same local axes as the meshes.
export const DESK_PLACEMENTS = {
  near_window: {desk: [0, 0, -1.48, 0], chair: [0, 0, .18, 0], attach: 'D'},
  left_wall: {desk: [-3.55, 0, .38, Math.PI / 2], chair: [-2.35, 0, .38, Math.PI / 2], attach: 'B'},
  right_wall: {desk: [3.45, 0, .12, -Math.PI / 2], chair: [2.25, 0, .12, -Math.PI / 2], attach: 'C1'},
  back_wall: {desk: [1.55, 0, -2.75, 0], chair: [1.55, 0, -1.35, 0], attach: 'C2'},
  center: {desk: [.22, 0, .55, 0], chair: [.22, 0, 1.98, 0], attach: 'H'},
  bedside: {desk: [-1.72, 0, -1.45, 0], chair: [-1.72, 0, -.08, 0], attach: 'B'},
};

export const BED_PLACEMENTS = {
  left_wall: [-3.25, 0, .05, 0],
  right_wall: [3.35, 0, .15, Math.PI],
  back_wall: [1.65, 0, -2.25, -Math.PI / 2],
  center: [.25, 0, 1.15, 0],
  near_window: [.15, 0, -1.95, -Math.PI / 2],
};

export function furniturePoint([x, y, z, yaw], dx, dy, dz) {
  return [x + dx * Math.cos(yaw) + dz * Math.sin(yaw), y + dy, z - dx * Math.sin(yaw) + dz * Math.cos(yaw)];
}
