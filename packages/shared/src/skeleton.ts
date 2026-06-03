/** COCO-17 skeleton constants shared by the overlay renderers. */

export const COCO17_NAMES = [
  "nose", "left_eye", "right_eye", "left_ear", "right_ear",
  "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
  "left_wrist", "right_wrist", "left_hip", "right_hip",
  "left_knee", "right_knee", "left_ankle", "right_ankle",
] as const;

export const SKELETON_EDGES: [number, number][] = [
  [5, 7], [7, 9],
  [6, 8], [8, 10],
  [5, 6],
  [5, 11], [6, 12],
  [11, 12],
  [11, 13], [13, 15],
  [12, 14], [14, 16],
  [0, 5], [0, 6],
];

export const LEFT_INDICES = [1, 3, 5, 7, 9, 11, 13, 15];
export const RIGHT_INDICES = [2, 4, 6, 8, 10, 12, 14, 16];

/** Lower-body joints most relevant to gait, for emphasis in the overlay. */
export const GAIT_KEYPOINTS = [11, 12, 13, 14, 15, 16];
