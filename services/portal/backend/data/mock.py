dashboard_data = [
    {
        "uuid": "uoa-abi-xxx_programme-001",
        "category": 'Programmes',
        "name": '12 LABOURS',
        "description": 'From mathematical modelling to proactive medicine.',
        "children": [
            {
                "uuid": "uoa-abi-xxx-project-001",
                "category": 'Projects',
                "name": 'EP4: Breast Biomechanics Project',
                "description": 'Integrating medical imaging, machine learning, and modeling to improve breast cancer diagnosis and treatment.',
                "children": [
                    {
                        "uuid": "uoa-abi-xxx-investigation-001",
                        "category": 'Investigations',
                        "name": 'Automated tumour position reporting',
                        "description": "Using workflow for breast tumour reporting",
                        "children": [
                            {
                                "uuid": "uoa-abi-xxx-study-001",
                                "category": 'Studies',
                                "name": 'Efficacy assessment of automated tumour position reporting workflow (single-site)',
                                "description": 'This study involves assessing the efficacy of automated and assisted workflows for tumour position reporting, compared with manual reporting.',
                                "children": [
                                    {
                                        "uuid": "uoa-abi-xxx-assay-001",
                                        "category": 'Assays',
                                        "name": 'Assay 1: Run workflow 1 on Duke University breast MRI dataset',
                                        "description": 'Using workflow 1: automated tumour position reporting (Model Generation)',
                                        "children": []
                                    },
                                    {
                                        "uuid": "uoa-abi-xxx-assay-002",
                                        "category": 'Assays',
                                        "name": 'Assay 2: Run workflow 4 on Duke University breast MRI dataset',
                                        "description": 'Using workflow 4: tumour position selection',
                                        "children": []
                                    },
                                    {
                                        "uuid": "uoa-abi-xxx-assay-003",
                                        "category": 'Assays',
                                        "name": 'Assay 3: Run workflow 2 on Duke University breast MRI dataset',
                                        "description": 'Using workflow 2: automated tumour position reporting (GUI)',
                                        "children": []
                                    },
                                    {
                                        "uuid": "uoa-abi-xxx-assay-004",
                                        "category": 'Assays',
                                        "name": 'Assay 4: Run workflow 3 on Duke University breast MRI dataset',
                                        "description": 'Using workflow 3: manual tumour position reporting',
                                        "children": []
                                    },
                                    {
                                        "uuid": "uoa-abi-xxx-assay-005",
                                        "category": 'Assays',
                                        "name": 'Assay 5: Run workflow 5 on Duke University breast MRI dataset',
                                        "description": 'Using workflow 5: assisted tumour position reporting',
                                        "children": []
                                    }
                                ]
                            },
                        ]

                    }
                ]
            }
        ]
    },
    {
        "uuid": "uoa-abi-xxx_programme-002",
        "category": 'Programmes',
        "name": 'Breast Biomechanics Research',
        "description": 'From mathematical modelling to proactive medicine.',
        "children": []}
]

workflows_data = [
    {
        "uuid": "xxxx-1234-uoa-abi-1",
        "name": "Automated tumour position reporting",
        "type": "Model Generation",
        "inputs": ["MRI Images", "Segmentation"],
        "outputs": ["Nifti Image", "NRRD Image", "Segmentation", "Point Could", "Mesh"],
    },
    {
        "uuid": "xxxx-1234-uoa-abi-2",
        "name": "Automated tumour position reporting",
        "type": "GUI",
        "inputs": ["MRI(NRRD)"],
        "outputs": ["Tumour Positions"],
    },
    {
        "uuid": "xxxx-1234-uoa-abi-3",
        "name": "Manual tumour position reporting",
        "type": "GUI",
        "inputs": [],
        "outputs": [],
    },
    {
        "uuid": "xxxx-1234-uoa-abi-4",
        "name": "Tumour position selection",
        "type": "GUI",
        "inputs": ["NRRD Image", "Tumour Center", "Tumour Bounding Box"],
        "outputs": ["Tumour Position"],
    },
    {
        "uuid": "xxxx-1234-uoa-abi-5",
        "name": "Assisted tumour position reporting",
        "type": "GUI",
        "inputs": [],
        "outputs": [],
    },
    {
        "uuid": "xxxx-1234-uoa-abi-6",
        "name": "Automated tumour extent reporting",
        "type": "Model Generation",
        "inputs": [],
        "outputs": [],
    },
    {
        "uuid": "xxxx-1234-uoa-abi-7",
        "name": "Automated tumour extent reporting",
        "type": "GUI",
        "inputs": [],
        "outputs": [],
    },
    {
        "uuid": "xxxx-1234-uoa-abi-8",
        "name": "Manual tumour extent reporting",
        "type": "GUI",
        "inputs": [],
        "outputs": [],
    },
    {
        "uuid": "xxxx-1234-uoa-abi-9",
        "name": "Tumour extent selection",
        "type": "GUI",
        "inputs": [],
        "outputs": [],
    },
    {
        "uuid": "xxxx-1234-uoa-abi-10",
        "name": "Assisted tumour extent reporting",
        "type": "GUI",
        "inputs": [],
        "outputs": [],
    }
]

datasets_data = [
    {
        "uuid": "xxxx-1234-uoa-abi-dataset-1",
        "name": "SPARC-dataset-1",
        "samples": [
            {
                "uuid": "xxxx-1234-uoa-abi-dataset-1-subject-1-sample-1",
                "name": "Sample-1",
            },
            {
                "uuid": "xxxx-1234-uoa-abi-dataset-1-subject-1-sample-2",
                "name": "Sample-2",
            }
        ]
    },
    {
        "uuid": "xxxx-1234-uoa-abi-dataset-2",
        "name": "SPARC-dataset-2",
        "samples": [
            {
                "uuid": "xxxx-1234-uoa-abi-dataset-2-subject-1-sample-1",
                "name": "Sample-1",
            },
            {
                "uuid": "xxxx-1234-uoa-abi-dataset-2-subject-1-sample-2",
                "name": "Sample-2",
            }
        ]
    }
]

assays_data = {}

launch_workflow = {
    "xxxx-1234-uoa-abi-1": {
        "type": "airflow",
        "url": "https://airflow.apache.org/"
    },
    "xxxx-1234-uoa-abi-2": {
        "type": "GUI",
        "url": None
    },
    "xxxx-1234-uoa-abi-3": {
        "type": "GUI",
        "url": None
    },
    "xxxx-1234-uoa-abi-4": {
        "type": "GUI",
        "url": "TumourCenterStudy"
    },
    "xxxx-1234-uoa-abi-5": {
        "type": "GUI",
        "url": None
    },
    "xxxx-1234-uoa-abi-6": {
        "type": "GUI",
        "url": None
    },
    "xxxx-1234-uoa-abi-7": {
        "type": "GUI",
        "url": None
    },
    "xxxx-1234-uoa-abi-8": {
        "type": "GUI",
        "url": None
    },
    "xxxx-1234-uoa-abi-9": {
        "type": "GUI",
        "url": None
    },
    "xxxx-1234-uoa-abi-10": {
        "type": "GUI",
        "url": None
    },
}
