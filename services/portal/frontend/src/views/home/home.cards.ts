import clinicalImage from '@/assets/dashboard/clinical-01.jpg';
import studyImage from '@/assets/dashboard/study.png';
import catelogueImage from '@/assets/dashboard/catalogue.png';
import tutorialImage from '@/assets/dashboard/how-to-use.png';
import mydigitaltwinImage from '@/assets/dashboard/my_digitaltwin.png';
import mydigitaltwinNavImage from '@/assets/dashboard/my-digital-twin-nav.jpg';
import fcMapImage from '@/assets/dashboard/fc-map.jpg';
import annotatorImage from '@/assets/dashboard/annotator.jpg';
import digitalRepositoryImage from '@/assets/dashboard/digital-repository.jpg';

export type CardConfig = {
    title: string;
    image: string;
    location: string;
    description: string;
    requireRoles?: string[];
    action?: { type: 'route'; name: string; params?: Record<string, string> } | { type: 'external'; url: string };
};

export const cards: CardConfig[] = [
    {
        title: 'How to use this platform',
        image: tutorialImage,
        location: 'Auckland Bioengineering Institute',
        description: 'Provides help and tutorials describing how to use the platform.',
        action: { type: 'route', name: 'TutorialDashboard' }
    },
    {
        title: 'Catalogue',
        image: catelogueImage,
        location: 'Auckland Bioengineering Institute',
        description: 'Provides “yellow pages” that enable users to see what AI/digital twin assets are being developed in research programmes. This includes viewing or adding new programmes, projects, investigations, studies, assays, workflows, measurements, and models.',
        requireRoles: [],
        action: { type: 'route', name: 'CatalogueDashboardView' }
    },
    {
        title: 'Study dashboard',
        image: studyImage,
        location: 'Te Whatu Ora AI Lab',
        description: 'Enables clinicians to collaborate with researchers to assess efficacy of AI/digital twin driven workflows.',
        requireRoles: ['admin', 'researcher'],
        action: { type: 'route', name: 'StudyDashboard' }
    },
    {
        title: 'Clinician dashboard',
        image: clinicalImage,
        location: 'Te Whatu Ora AI Lab',
        description: 'Enables clinicians to run AI/digital twin driven workflows and generate clinical reports.',
        requireRoles: ['admin', 'researcher', 'clinician'],
        action: { type: 'route', name: 'ClinicianDashboard' }
    },
    {
        title: 'Physiology exploration (FC Map)',
        image: fcMapImage,
        location: 'SPARC',
        description: 'Use the FC Map to explore physics informed biomedical models.',
        action: { type: 'external', url: 'https://mapcore-demo.org/2024/sparc-app-isan/apps/maps?id=f2a99cd3' }
    },
    {
        title: 'My digital twin',
        image: mydigitaltwinImage,
        location: 'Te Whatu Ora',
        description: 'Enables patients to interact with their digital twins to better understand and manage their medical conditions.',
        action: { type: 'external', url: 'https://abi-web-apps.github.io/' }
    },
    {
        title: 'DigitalTWINS data repository',
        image: digitalRepositoryImage,
        location: 'Auckland Bioengineering Institute',
        description: 'World’s first data resource where health information from participants across multiple research studies can be contributed, linked, and reused with informed consent for developing digital twins.',
        action: { type: 'external', url: import.meta.env.VITE_SEEK_URL || 'http://130.216.216.26:8001/' }
    },
    {
        title: 'My digital health navigator',
        image: mydigitaltwinNavImage,
        location: 'Auckland Bioengineering Institute',
        description: 'Interact with your digital health navigator (DiNa).',
        action: { type: 'external', url: 'https://dina.kekayan.com/' }
    },
    {
        title: 'Medical image annotation',
        image: annotatorImage,
        location: 'Auckland Bioengineering Institute',
        description: 'Efficiently annotate medical images using advanced AI-assisted workflows.',
        action: { type: 'external', url: 'https://build-seven-iota.vercel.app/#/' }
    }
];
