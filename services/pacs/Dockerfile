FROM orthancteam/orthanc:26.6.0

# Install pydicom for DICOM tag manipulation in the Python plugin
RUN pip install --break-system-packages --no-cache-dir "pydicom<3" "dicom-anonymizer>=1.0.13"
