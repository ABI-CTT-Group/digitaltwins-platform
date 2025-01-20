const eventNames = [
    "Core:NrrdTools",
    'TumourStudy:Casename', 
    'TumourStudy:Status', 
    "TumourStudy:NextCase", 
    "TumourStudy:ImageLoaded", 
    "TumourStudy:CaseReport", 
    "TumourStudy:AllCasesCompleted", 
    "TumourStudy:UpdateTumourPosition",
    "TumourStudy:UpdateSkinPosition",
    "TumourStudy:UpdateRibcagePosition",
    "TumourStudy:UpdateClosestNipplePosition",
    "Segmentation:CaseDetails",
    "Segementation:CaseSwitched",
    "Segmentation:ContrastChanged",
    "Segmentation:RegisterImageChanged",
    "Segmentation:RegisterButtonStatusChanged",
    "Segmentation:ContrastImageStates",
    "Segmentation:FinishLoadAllCaseImages",
    "Segmentation:SyncTumourModelButtonClicked",
    "SegmentationTrial:CalulatorTimerFunction",
    "SegmentationTrial:DrawSphereFunction",
    "Common:NavStickyMode",
    "Common:DebugMode",
    "Common:DrawerStatus",
    "Common:ResizeCopperSceneWhenNavChanged",
    "Common:CloseCalculatorBox",
    "Common:OpenCalculatorBox",
    "Common:DragImageWindowCenter",
    "Common:DragImageWindowHigh",
    "Common:ToggleAppTheme",
    "Common:ToggleBreastVisibility",
    "Common:OnAppMounted",
    "IntroGuide:OperationStatus",
    "IntroGuide:DrawerStatus",
];
type EventNames = (typeof eventNames)[number];

const generateEventListeners = () => {
    const listeners: Record<string, Set<Function>> = {};
    eventNames.forEach(eventName => {
        listeners[eventName] = new Set();
    });
    return listeners;
};


class EventEmitter {
    private listeners: Record<string, Set<Function>> = generateEventListeners();

    on(eventName: EventNames, listener: Function) {
        if (eventNames.includes(eventName)) {
            this.listeners[eventName].add(listener);
        }
    }

    off(eventName: EventNames, listener: Function) {
        if (eventNames.includes(eventName)) {
            this.listeners[eventName].delete(listener);
        }
    }

    emit(eventName: EventNames, ...args: any[]) {
        if (eventNames.includes(eventName)) {
            this.listeners[eventName].forEach(listener => listener(...args));
        }
    }
}

export default new EventEmitter();