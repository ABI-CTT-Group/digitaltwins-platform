import { IDashboardData } from '@/models/uiTypes';
export const dashboardData:IDashboardData= [
    {
        category: 'Programmes',
        name: '12 LABOURS',
        description: 'From mathematical modelling to proactive medicine.',
        children: [
            {   
                category: 'Projects',
                name: 'EP4: Breast Biomechanics Project',
                description: 'Integrating medical imaging, machine learning, and modeling to improve breast cancer diagnosis and treatment.',
                children:[
                    {
                        category: 'Investigations',
                        name: 'Automated tumour position reporting',
                        description: "Using workflow for breast tumour reporting",
                        children: [
                            {
                                category: 'Studies',
                                name: 'Efficacy assessment of automated tumour position reporting workflow (single-site)',
                                description: 'This study involves assessing the efficacy of automated and assisted workflows for tumour position reporting, compared with manual reporting.',
                                children: [
                                    {
                                        category: 'Assays',
                                        name: 'Assay 1: Run workflow 1 on Duke University breast MRI dataset',
                                        description: 'Using workflow 1: automated tumour position reporting (Model Generation)',
                                        children:[
                                            {
                                                category: "SOP",
                                                name: "Tumour Position Study",
                                                children: [
                                                    {
                                                        studies:[
                                                            {
                                                                name: 'Tumour Position Study',
                                                                subTitle: "Cases: 100",
                                                                description: 'Calculate tumour distance to the skin, ribcage, and nipple mannually',
                                                                src: 'https://cdn.vuetifyjs.com/images/cards/docks.jpg',
                                                                status: 'active',
                                                                isEnter: false,
                                                                session: "TumourCalaulationStudy"
                                                            },
                                                            {
                                                                name: 'Tumour Center Manual Correction',
                                                                subTitle: "Cases: 100",
                                                                description: 'Give tumour center at bounding box, and correct the center mannually',
                                                                src: 'https://cdn.vuetifyjs.com/images/carousel/planet.jpg',
                                                                status: 'active',
                                                                isEnter: false,
                                                                session: "TumourCenterStudy"
                                                            },  
                                                        ],
                                                    },
                                                    {
                                                        studies:[ 
                                                            {
                                                                name: 'Tumour Study Assisted Manually',
                                                                subTitle: "Cases: 100",
                                                                description: 'Assist to change tumour, skin, ribcage, and nipple position',
                                                                src: 'https://cdn.vuetifyjs.com/images/carousel/sky.jpg',
                                                                status: 'active',
                                                                isEnter: false,
                                                                session: "TumourAssistedStudy"
                                                            }
                                                        ],
                                                    }
                                                ]
                                            },
                                            {
                                                category: "SOP",
                                                name: "Tumour segmentation Study",
                                                children: [
                                                    {
                                                        studies:[ 
                                                            {
                                                                name: 'Tumour Position & Extent Report',
                                                                subTitle: "Cases: 100",
                                                                description: 'Using tools to segment tumour and generate a report',
                                                                src: 'https://cdn.vuetifyjs.com/images/cards/sunshine.jpg',
                                                                status: 'active',
                                                                isEnter: false,
                                                                session: "TumourSegmentationStudy"
                                                            },
                                                        ],
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        category: 'Assays',
                                        name: 'Assay 2: Run workflow 4 on Duke University breast MRI dataset',
                                        description: 'Using workflow 4: tumour position selection',
                                        children:[]
                                    },
                                    {
                                        category: 'Assays',
                                        name: 'Assay 3: Run workflow 2 on Duke University breast MRI dataset',
                                        description: 'Using workflow 2: automated tumour position reporting (GUI)',
                                        children:[]
                                    },
                                    {
                                        category: 'Assays',
                                        name: 'Assay 4: Run workflow 3 on Duke University breast MRI dataset',
                                        description: 'Using workflow 3: manual tumour position reporting',
                                        children:[]
                                    },
                                    {
                                        category: 'Assays',
                                        name: 'Assay 5: Run workflow 5 on Duke University breast MRI dataset',
                                        description: 'Using workflow 5: assisted tumour position reporting',
                                        children:[]
                                    }
                                ]
                            }, 
                        ]
                        
                    }
                ]
            }
        ]
    }
]

export const workflowsData = [
    {   
        uuid: "xxxx-1234-uoa-abi-1",
        name: "Automated tumour position reporting",
        type: "Model Generation",
        inputs:["MRI Images", "Segmentation"],
        outputs: ["Mesh"],
    },
    {
        uuid: "xxxx-1234-uoa-abi-2",
        name: "Automated tumour position reporting",
        type: "GUI",
        inputs:[],
        outputs: [],
    },
    {
        uuid: "xxxx-1234-uoa-abi-3",
        name: "Manual tumour position reporting",
        type: "GUI",
        inputs:[],
        outputs: [],
    },
    {
        uuid: "xxxx-1234-uoa-abi-4",
        name: "Tumour position selection",
        type: "GUI",
        inputs:[],
        outputs: [],
    },
    {
        uuid: "xxxx-1234-uoa-abi-5",
        name: "Assisted tumour position reporting",
        type: "GUI",
        inputs:[],
        outputs: [],
    },
    {
        uuid: "xxxx-1234-uoa-abi-6",
        name: "Automated tumour extent reporting",
        type: "Model Generation",
        inputs:[],
        outputs: [],
    },
    {
        uuid: "xxxx-1234-uoa-abi-7",
        name: "Automated tumour extent reporting",
        type: "GUI",
        inputs:[],
        outputs: [],
    },
    {
        uuid: "xxxx-1234-uoa-abi-8",
        name: "Manual tumour extent reporting",
        type: "GUI",
        inputs:[],
        outputs: [],
    },
    {
        uuid: "xxxx-1234-uoa-abi-9",
        name: "Tumour extent selection",
        type: "GUI",
        inputs:[],
        outputs: [],
    },
    {
        uuid: "xxxx-1234-uoa-abi-10",
        name: "Assisted tumour extent reporting",
        type: "GUI",
        inputs:[],
        outputs: [],
    }
]

export const datasetsData = [
    {
        uuid: "xxxx-1234-uoa-abi-dataset-1",
        name: "SPARC-dataset-1",
        samples: [
            {
                uuid: "xxxx-1234-uoa-abi-dataset-1-subject-1-sample-1",
                name: "Sample-1",
            },
            {
                uuid: "xxxx-1234-uoa-abi-dataset-1-subject-1-sample-2",
                name: "Sample-2",
            }
        ]
    },
    {
        uuid: "xxxx-1234-uoa-abi-dataset-2",
        name: "SPARC-dataset-2",
        samples: [
            {
                uuid: "xxxx-1234-uoa-abi-dataset-2-subject-1-sample-1",
                name: "Sample-1",
            },
            {
                uuid: "xxxx-1234-uoa-abi-dataset-2-subject-1-sample-2",
                name: "Sample-2",
            }
        ]
    }
]