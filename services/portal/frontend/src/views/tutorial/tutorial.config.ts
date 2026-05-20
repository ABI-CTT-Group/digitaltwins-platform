export type SectionItem = { title: string; herf: string; width: number };

export type SectionConfig = {
    title: string;
    items: SectionItem[];
};

export const sections: SectionConfig[] = [
    {
        title: 'Help documentation',
        items: [
            {
                title: 'How to use the study dashboard',
                herf: 'https://github.com/ABI-CTT-Group/DigitalTWINS-Portal?tab=readme-ov-file#how-to-use-the-study-dashboard',
                width: 350,
            },
            {
                title: 'How to create and upload datasets',
                herf: 'https://copper3d-brids.github.io/ehr-docs/docs/ehr/literature-review/data%20de-identification#de-identifying-dicom-data-with-hipaa',
                width: 350,
            }
        ]
    },
    {
        title: 'API documentation',
        items: [
            {
                title: 'DigitalTWINS-API',
                herf: import.meta.env.VITE_API_DOC_DT_URL,
                width: 350,
            },
            {
                title: 'DigitalTWINS-Portal-API',
                herf: import.meta.env.VITE_API_DOC_PORTAL_URL,
                width: 350,
            }
        ]
    },
    {
        title: 'Guidelines',
        items: [
            {
                title: 'Computational physiology workflows',
                herf: 'https://docs.google.com/document/d/1ArbBXdzKCbM_ED5fDBR9yqC2KGp-1Hl7wrrV29ABB1k/edit?tab=t.0#heading=h.c87qz8f8iu38',
                width: 350
            }
        ]
    },
    {
        title: 'Resources',
        items: [
            {
                title: 'DigitalTWINS on FHIR',
                herf: 'https://colab.research.google.com/drive/15c_v9sK4wSF3Rng3j6xk-L6ngfWEEbPq',
                width: 350
            },
            {
                title: 'Clinical Description Annotator',
                herf: 'https://colab.research.google.com/drive/1rMgA9ycJHyQ1owI-vRyIquIVOU5eAjIF#scrollTo=oAw8vVmP2AWj',
                width: 350
            },
            {
                title: 'Sparc-me',
                herf: 'https://github.com/SPARC-FAIR-Codeathon/sparc-me/tree/main?tab=readme-ov-file#sparc-metadata-editor-sparc-me',
                width: 350
            }
        ]
    }
];
