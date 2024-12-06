const eventNames = ['TumourStudy:Casename', 'TumourStudy:Status', "TumourStudy:NextCase", "TumourStudy:ImageLoaded", "TumourStudy:NrrdTools", ];
type EventNames = (typeof eventNames)[number];

class EventEmitter {
    private listeners: Record<string, Set<Function>> = {
        'TumourStudy:Casename': new Set(),
        'TumourStudy:Status': new Set(),
        'TumourStudy:NextCase': new Set(),
        'TumourStudy:ImageLoaded': new Set(),
        'TumourStudy:NrrdTools': new Set(),
    };

    on(eventName: EventNames, listener: Function) {
        if (eventNames.includes(eventName)) {
            this.listeners[eventName].add(listener);
        }
    }

    emit(eventName: EventNames, ...args: any[]) {
        if (eventNames.includes(eventName)) {
            this.listeners[eventName].forEach(listener => listener(...args));
        }
    }
}

export default new EventEmitter();