import { ILoadUrls } from "@/models/apiTypes";
import * as THREE from "three";
import eraser_1 from "@/assets/eraser/circular-cursor_3.png";
import eraser_2 from "@/assets/eraser/circular-cursor_8.png";
import eraser_3 from "@/assets/eraser/circular-cursor_13.png";
import eraser_4 from "@/assets/eraser/circular-cursor_18.png";
import eraser_5 from "@/assets/eraser/circular-cursor_23.png";
import eraser_6 from "@/assets/eraser/circular-cursor_28.png";
import eraser_7 from "@/assets/eraser/circular-cursor_33.png";
import eraser_8 from "@/assets/eraser/circular-cursor_38.png";
import eraser_9 from "@/assets/eraser/circular-cursor_43.png";
import eraser_10 from "@/assets/eraser/circular-cursor_48.png";
import eraser_11 from "@/assets/eraser/circular-cursor_52.png";
import cursor_dot from "@/assets/cursor/dot.svg";

type ITemp = {
  name: string;
  masked: boolean;
  has_mesh: boolean;
};

export function findCurrentCase(caseDetail: ITemp[], currentCaseName: string) {
  const result = caseDetail.filter((item) => {
    return item.name === currentCaseName;
  });
  return result[0];
}

export function revokeAppUrls(revokeUrls: ILoadUrls) {
  for (let key in revokeUrls) {
    const jsonUrl = revokeUrls[key].jsonUrl;
    const urls = revokeUrls[key].nrrdUrls as Array<string>;
    urls.forEach((url) => {
      URL.revokeObjectURL(url);
    });
    URL.revokeObjectURL(jsonUrl);
  }
}

export function revokeRegisterNrrdImages(regUrls: string[]) {
  regUrls.forEach((url) => {
    URL.revokeObjectURL(url);
  });
}

export function getEraserUrlsForOffLine() {
  const urls = [
    eraser_1,
    eraser_2,
    eraser_3,
    eraser_4,
    eraser_5,
    eraser_6,
    eraser_7,
    eraser_8,
    eraser_9,
    eraser_10,
    eraser_11,
  ];
  return urls;
}

export function getCursorUrlsForOffLine() {
  const urls = [cursor_dot];
  return urls;
}

export function transformMeshPointToImageSpace(
  x: number[],
  origin: number[],
  spacing: number[],
  dimensions: number[],
  bias: THREE.Vector3
) {
  const z = [
    -x[1] + origin[0] + spacing[0] * dimensions[0] + bias.x,
    x[0] + origin[1] + bias.y,
    x[2] + origin[2] + bias.z,
  ];
  return z;
}

export function createOriginSphere(
  origin: number[],
  ras: number[],
  spacing: number[],
  x_bias: number,
  y_bias: number,
  z_bias: number
) {
  const geometry = new THREE.SphereGeometry(5, 32, 16);
  const materiallt = new THREE.MeshBasicMaterial({ color: "red" });
  const materialrt = new THREE.MeshBasicMaterial({ color: "skyblue" });
  const materiallb = new THREE.MeshBasicMaterial({ color: "grey" });
  const materialrb = new THREE.MeshBasicMaterial({ color: "dark" });
  const spherelt = new THREE.Mesh(geometry, materiallt);
  const spherert = new THREE.Mesh(geometry, materialrt);
  const spherelb = new THREE.Mesh(geometry, materiallb);
  const sphererb = new THREE.Mesh(geometry, materialrb);

  const resetOrigin = [
    origin[0] + x_bias,
    origin[1] + y_bias,
    origin[2] + z_bias,
  ];
  
  spherelt.position.set(resetOrigin[0], resetOrigin[1], resetOrigin[2]);
  spherert.position.set(
    resetOrigin[0] + ras[0],
    resetOrigin[1],
    resetOrigin[2]
  );
  spherelb.position.set(
    resetOrigin[0],
    resetOrigin[1] + ras[1],
    resetOrigin[2]
  );
  sphererb.position.set(
    resetOrigin[0] + ras[0],
    resetOrigin[1] + ras[1],
    resetOrigin[2]
  );

  return [spherelt, spherert, spherelb, sphererb];
}

export function getFormattedTime(time: number) {
  let timeStr = "";
  let hour = Math.floor(time);
  if (hour === 0) hour = 12;
  let min = Math.round(60 * (time - Math.floor(time)));
  if (min < 15) {
    min = 0;
  } else if (min < 45) {
    min = 30;
  } else {
    min = 0;
    hour += 1;
  }
  if (min < 10) {
    timeStr = hour.toFixed(0) + ":0" + min;
  } else {
    timeStr = hour.toFixed(0) + ":" + min;
  }
  return timeStr;
}

export function getClosestNipple(
  nippleLeft: THREE.Vector3,
  nippleRight: THREE.Vector3,
  tumourCenter: THREE.Vector3
) {
  let distLeft = tumourCenter.distanceTo(nippleLeft);
  let distRight = tumourCenter.distanceTo(nippleRight);

  if (distLeft < distRight) {
    const { rd, angle, time } = getNippleClock(tumourCenter, nippleLeft);
    const p = rd < 10 ? "central" : "L";
    return {
      dist: "L: " + distLeft.toFixed(0),
      angle,
      time,
      timeStr: getFormattedTime(time),
      radial_distance: rd,
      p,
    };
  } else {
    const { rd, angle, time } = getNippleClock(tumourCenter, nippleRight);
    const p = rd < 10 ? "central" : "R";
    return {
      dist: "R: " + distRight.toFixed(0),
      angle,
      time,
      timeStr: getFormattedTime(time),
      radial_distance: rd,
      p,
    };
  }
}

function getNippleClock(tumourCenter: THREE.Vector3, nipplePos: THREE.Vector3) {
  let dx = tumourCenter.x - nipplePos.x;
  let dy = tumourCenter.y - nipplePos.y;
  let dz = tumourCenter.z - nipplePos.z;

  let rd = Math.sqrt(dx * dx + dz * dz);
  let angle = Math.atan2(-dx, -dz);
  let time = 6 + (12 * angle) / (2 * Math.PI);

  return { rd, angle, time };
}

export function throttle(callback: (event: MouseEvent) => void, wait: number) {
  let start: number = 0;
  return function (event: MouseEvent) {
    const current: number = Date.now();
    if (current - start > wait) {
      callback.call(null, event);
      start = current;
    }
  };
}



export function throttle2(func:Function, delay:number) {
  let lastExecTime = 0;
  let timeoutId:any;

  return function (...args:any[]) {
    const currentTime = Date.now();

    if (currentTime - lastExecTime >= delay) {
      func(...args);
      lastExecTime = currentTime;
    } else {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        func(...args);
        lastExecTime = currentTime;
      }, delay);
    }
  };
}