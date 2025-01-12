import * as Copper from "copper3d";
import * as THREE from "three";
import { getClosestNipple } from "@/plugins/view-utils/tools";
import { IRequests, IDetails } from "@/models/apiTypes";
export class PanelOperationManager {
  operator: HTMLElement;
  private operatorId: string;
  private started: boolean = false;
  private slicePrams = {
    maxIndex: 0,
    spaceRatio: 0,
    currentViewedSlice: null,
    currentSliceIndex: 0,
  };
  private dragPrams = {
    move: 0,
    y: 0,
    h: 0,
    sensitivity: 1,
    handleOnDragMouseUp: (ev: MouseEvent) => {},
    handleOnDragMouseMove: (ev: MouseEvent) => {},
    handleOnDragMouseDown: (ev: MouseEvent) => {},
  };

  constructor(operator: HTMLElement) {
    this.operator = operator;
    this.operatorId = operator.id;
  }

  setSlicePrams(currentSlice: any) {
    this.slicePrams.maxIndex = currentSlice.MaxIndex;
    this.slicePrams.currentViewedSlice = currentSlice;
    this.slicePrams.currentSliceIndex = Math.ceil(
      currentSlice.index / currentSlice.RSARatio
    );
    this.slicePrams.spaceRatio = currentSlice.RSARatio;
  }

  start() {
    if (!this.started) {
      this.dragPrams.h = this.operator.offsetHeight;
      this.dragPrams.handleOnDragMouseDown = this.handleMouseDown();
      this.dragPrams.handleOnDragMouseMove = this.handleMouseMove();
      this.dragPrams.handleOnDragMouseUp = this.handleMouseUp();
      this.operator.addEventListener(
        "mousedown",
        this.dragPrams.handleOnDragMouseDown
      );
      this.operator.addEventListener(
        "mouseup",
        this.dragPrams.handleOnDragMouseUp
      );
      this.started = true;
    }
  }

  dispose() {
    this.operator.removeEventListener(
      "mousedown",
      this.dragPrams.handleOnDragMouseDown
    );
    this.operator.removeEventListener(
      "mousemove",
      this.dragPrams.handleOnDragMouseMove
    );
    this.operator.removeEventListener(
      "mouseup",
      this.dragPrams.handleOnDragMouseUp
    );
    this.started = false;
  }

  setDragSensitivity(s: number) {
    if (typeof s !== "number") return;
    if (s <= 0) {
      this.dragPrams.sensitivity = 1;
      return;
    } else if (s > 20) {
      this.dragPrams.sensitivity = 20;
      return;
    } else {
      this.dragPrams.sensitivity = s;
    }
  }

  private handleMouseDown() {
    return (ev: MouseEvent) => {
      if (ev.button === 0) {
        // left click
        this.dragPrams.y = ev.offsetY / this.dragPrams.h;
        this.operator.addEventListener(
          "mousemove",
          this.dragPrams.handleOnDragMouseMove
        );
      }
    };
  }
  private handleMouseMove() {
    return Copper.throttle((ev: MouseEvent) => {
      if (ev.button === 0) {
        if (this.dragPrams.y - ev.offsetY / this.dragPrams.h >= 0) {
          this.dragPrams.move = -Math.ceil(
            ((this.dragPrams.y - ev.offsetY / this.dragPrams.h) * 10) /
              this.dragPrams.sensitivity
          );
        } else {
          this.dragPrams.move = -Math.floor(
            ((this.dragPrams.y - ev.offsetY / this.dragPrams.h) * 10) /
              this.dragPrams.sensitivity
          );
        }
        this.dragPrams.y = ev.offsetY / this.dragPrams.h;
        this.updateSliceIndex(this.dragPrams.move);
      }
    }, this.dragPrams.sensitivity * 200);
  }

  private handleMouseUp() {
    return (ev: MouseEvent) => {
      this.operator.removeEventListener(
        "mousemove",
        this.dragPrams.handleOnDragMouseMove
      );
    };
  }

  updateSliceIndex(move: number) {
    const currentSlice = this.slicePrams.currentViewedSlice as any;
    let newIndex = this.slicePrams.currentSliceIndex + move;
    if (newIndex > this.slicePrams.maxIndex) {
      newIndex = this.slicePrams.maxIndex;
    } else if (newIndex < 0) {
      newIndex = 0;
    }

    currentSlice.index = newIndex * this.slicePrams.spaceRatio;
    currentSlice.repaint.call(currentSlice);
    this.slicePrams.currentSliceIndex = newIndex;
  }
}

export function valideClock(
  start: boolean,
  copperScene: Copper.copperScene,
  bg: HTMLElement,
  tl?: any,
  tr?: any,
  nrrdMesh?: any
) {
  let oldPoint: any;
  const geometry = new THREE.SphereGeometry(5, 32, 16);
  const material = new THREE.MeshBasicMaterial({ color: "green" });
  const validCore = (ev: MouseEvent) => {
    if (!!oldPoint) {
      copperScene.scene.remove(oldPoint);
    }
    const x = ev.offsetX;
    const y = ev.offsetY;
    const p = copperScene.pickSpecifiedModel(
      [nrrdMesh.x, nrrdMesh.y, nrrdMesh.z],
      { x, y }
    );
    oldPoint = new THREE.Mesh(geometry, material);
    oldPoint.name = "valid point";
    copperScene.scene.add(oldPoint);
    const target = p.intersects.filter(
      (obj) => obj.object.name === "Cornal"
    )[0] as any;
    if (!!target) {
      oldPoint.position.set(target.point.x, target.point.y, target.point.z);
      const a = getClosestNipple(
        new THREE.Vector3(tl[0], tl[1], tl[2]),
        new THREE.Vector3(tr[0], tr[1], tr[2]),
        oldPoint.position
      );
      console.log(a);
    }
  };
  if (start) {
    bg.onclick = validCore;
  } else {
    bg.onclick = null;
    if (!!oldPoint) {
      copperScene.scene.remove(oldPoint);
    }
    copperScene.scene.traverse((mesh) => {
      if (mesh.name === "valid point") {
        copperScene.scene.remove(mesh);
      }
    });
  }
}

export function deepClone(obj: any, clonedObjects = new WeakMap()) {
  if (obj === null || typeof obj !== "object") {
    return obj;
  }

  if (clonedObjects.has(obj)) {
    return clonedObjects.get(obj);
  }

  let newObj: any = Array.isArray(obj) ? [] : {};

  clonedObjects.set(obj, newObj);

  for (let key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      newObj[key] = deepClone(obj[key], clonedObjects);
    }
  }

  return newObj;
}


export function processPointsCloud(points:number[][], bias: THREE.Vector3){
  const processedPoints:number[][] = []
  points.forEach((point)=>{
    processedPoints.push([point[0]+bias.x, point[1]+bias.y, point[2]+bias.z])
  })
  
   return processedPoints;

}

export const findBreastRequestUrls = (
  details: Array<IDetails>,
  caseId: string,
  type: "registration" | "origin"
) => {
  const currentCaseDetails = details.filter((item) => item.name === caseId)[0];
  const requests: Array<IRequests> = [];
  
  currentCaseDetails.file_paths.segmentation_breast_points_paths.forEach(
    (filepath) => {
      requests.push({
        url: "/single-file",
        params: { path: filepath },
      });
    }
  );
  currentCaseDetails.file_paths.segmentation_breast_model_paths.forEach(
    (filepath) => {
      requests.push({
        url: "/single-file",
        params: { path: filepath },
      });
    }
  );
  return requests;
};