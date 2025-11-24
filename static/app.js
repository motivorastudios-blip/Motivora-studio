import * as THREE from "https://unpkg.com/three@0.160.0/build/three.module.js";
    import { OrbitControls } from "https://unpkg.com/three@0.160.0/examples/jsm/controls/OrbitControls.js?module";
    import { STLLoader } from "https://unpkg.com/three@0.160.0/examples/jsm/loaders/STLLoader.js?module";

    const DEFAULT_QUALITY = (window.DEFAULT_QUALITY || "ultra").toLowerCase();
    const form = document.getElementById("upload-form");
    const submitButton = document.getElementById("submit-button");
    const statusLabel = document.getElementById("status-label");
    const progressBar = document.getElementById("progress-bar");
    const totalEta = document.getElementById("total-eta");
    const fileInput = document.getElementById("model");
    const axisSelect = document.getElementById("axis");
    const offsetInput = document.getElementById("offset");
    const autoCheckbox = document.getElementById("auto_orientation");
    const qualitySelect = document.getElementById("quality");
    const kelvinSelect = document.getElementById("kelvin");
    const autoBrightnessCheckbox = document.getElementById("auto_brightness");
    const exposureSlider = document.getElementById("exposure");
    const exposureValue = document.getElementById("exposure-value");
    const exposureField = document.getElementById("exposure-field");
    const viewerCanvas = document.getElementById("viewer");
    const viewerNote = document.getElementById("viewer-note");
    const previewButton = document.getElementById("preview-spin");
    const uploadSection = document.getElementById("upload-section");
    const progressSection = document.getElementById("progress-section");
    const cancelButton = document.getElementById("cancel-button");
    const downloadButton = document.getElementById("download-button");
    const uploadStatus = document.getElementById("upload-status");
    const summaryQuality = document.getElementById("summary-quality");
    const summaryOrientation = document.getElementById("summary-orientation");
    const summaryAxis = document.getElementById("summary-axis");
    const resetViewButton = document.getElementById("reset-view");

    const renderer = new THREE.WebGLRenderer({ canvas: viewerCanvas, antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(viewerCanvas.clientWidth, viewerCanvas.clientHeight, false);
    renderer.setClearColor(0x000000, 1);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      45,
      viewerCanvas.clientWidth / viewerCanvas.clientHeight,
      0.1,
      1000
    );
    const DEFAULT_CAMERA_POS = new THREE.Vector3(0, -4, 2.5);
    const DEFAULT_CAMERA_TARGET = new THREE.Vector3(0, 0, 0);
    camera.position.copy(DEFAULT_CAMERA_POS);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enablePan = false;
    controls.target.copy(DEFAULT_CAMERA_TARGET);
    controls.update();

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.65);
    scene.add(ambientLight);
    const keyLight = new THREE.DirectionalLight(0xfff2d4, 0.9);
    keyLight.position.set(3, -4, 5);
    scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(0xf8e7b0, 0.6);
    fillLight.position.set(-2.5, 3.5, 4);
    scene.add(fillLight);

    // Kelvin to RGB conversion function
    function kelvinToRGB(kelvin) {
      kelvin = Math.max(1000, Math.min(40000, kelvin));
      const temp = kelvin / 100.0;
      
      let red, green, blue;
      
      // Red component
      if (temp <= 66) {
        red = 255;
      } else {
        red = temp - 60;
        red = 329.698727446 * Math.pow(red, -0.1332047592);
        red = Math.max(0, Math.min(255, red));
      }
      
      // Green component
      if (temp <= 66) {
        green = temp;
        green = 99.4708025861 * Math.log(green) - 161.1195681661;
        green = Math.max(0, Math.min(255, green));
      } else {
        green = temp - 60;
        green = 288.1221695283 * Math.pow(green, -0.0755148492);
        green = Math.max(0, Math.min(255, green));
      }
      
      // Blue component
      if (temp >= 66) {
        blue = 255;
      } else if (temp <= 19) {
        blue = 0;
      } else {
        blue = temp - 10;
        blue = 138.5177312231 * Math.log(blue) - 305.0447927307;
        blue = Math.max(0, Math.min(255, blue));
      }
      
      return { r: red / 255, g: green / 255, b: blue / 255 };
    }

    // Update preview lighting based on Kelvin temperature (optimized)
    function updatePreviewLighting(kelvin) {
      const keyColor = kelvinToRGB(kelvin);
      keyLight.color.setRGB(keyColor.r, keyColor.g, keyColor.b);
      fillLight.color.setRGB(...kelvinToRGB(Math.min(10000, kelvin + 500)));
      renderPreview();
    }

    // Update preview brightness based on exposure value (optimized)
    function updatePreviewBrightness(exposure) {
      const factor = Math.pow(2, exposure);
      ambientLight.intensity = Math.max(0.1, Math.min(2.0, 0.65 * factor));
      keyLight.intensity = Math.max(0.2, Math.min(3.0, 0.9 * factor));
      fillLight.intensity = Math.max(0.1, Math.min(2.0, 0.6 * factor));
      renderPreview();
    }
    
    // Helper function to force preview render (optimized - single render call)
    function renderPreview() {
      if (meshGroup) {
        renderer.render(scene, camera);
      }
    }

    // Update lighting when Kelvin selector changes (simplified)
    if (kelvinSelect) {
      kelvinSelect.addEventListener("change", () => {
        const kelvin = parseInt(kelvinSelect.value) || 5600;
        updatePreviewLighting(kelvin);
      });
    }

    let meshGroup = null;
    const baseRotation = { x: 0, y: 0, z: 0 };
    const previewState = { active: false, startTime: null, duration: 4 };
    let currentDimensions = null;

    if (DEFAULT_QUALITY && ["fast", "standard", "ultra"].includes(DEFAULT_QUALITY)) {
      qualitySelect.value = DEFAULT_QUALITY;
    }

    function disposeObject(object) {
      object.traverse((child) => {
        if (child.isMesh) {
          child.geometry?.dispose();
          if (Array.isArray(child.material)) {
            child.material.forEach((mat) => mat.dispose?.());
          } else {
            child.material?.dispose?.();
          }
        }
      });
    }

    function formatEta(seconds) {
      if (typeof seconds !== "number" || !isFinite(seconds) || seconds <= 0) {
        return "";
      }
      const minutes = Math.floor(seconds / 60);
      const secs = Math.max(0, Math.round(seconds % 60));
      if (minutes > 0) {
        return `${minutes}m ${secs.toString().padStart(2, "0")}s`;
      }
      return `${secs}s`;
    }

    function showProgressView() {
      uploadSection.classList.add("hidden");
      progressSection.classList.remove("hidden");
      uploadStatus.textContent = "";
      progressBar.style.width = "0%";
      statusLabel.textContent = "Preparing Blender…";
      if (cancelButton) cancelButton.classList.remove("hidden");
      if (downloadButton) downloadButton.classList.add("hidden");
      updateBadgeSummary();
    }

    function showUploadView(message) {
      progressSection.classList.add("hidden");
      uploadSection.classList.remove("hidden");
      if (message) {
        uploadStatus.textContent = message;
      } else {
        uploadStatus.textContent = "";
      }
      statusLabel.textContent = "";
      progressBar.style.width = "0%";
      submitButton.disabled = false;
      if (cancelButton) cancelButton.classList.add("hidden");
      if (downloadButton) downloadButton.classList.add("hidden");
      currentJobId = null;
      updateBadgeSummary();
    }

    function clearPreview() {
      if (meshGroup) {
        scene.remove(meshGroup);
        disposeObject(meshGroup);
        meshGroup = null;
      }
      resetViewButton.disabled = true;
      resetView();
      renderer.render(scene, camera);
      previewButton.disabled = true;
      previewState.active = false;
      previewState.startTime = null;
    }

    function createMaterial() {
      return new THREE.MeshStandardMaterial({
        color: new THREE.Color(0xd8cfbc),
        roughness: 0.5,
        metalness: 0.05,
      });
    }

    function computeAutoOrientation(dimensions) {
      const dims = { ...dimensions };
      const maxXY = Math.max(dims.X, dims.Y);
      let axis;
      if (dims.Z >= maxXY * 1.2) {
        axis = "Z";
      } else {
        axis = ["X", "Y", "Z"].reduce((minAxis, candidate) => {
          return dims[candidate] < dims[minAxis] ? candidate : minAxis;
        }, "X");
      }

      let offset = 0;
      if (axis === "Z") {
        offset = dims.X >= dims.Y ? 0 : 90;
      } else if (axis === "Y") {
        offset = dims.X >= dims.Z ? 0 : 90;
      } else {
        offset = dims.Y >= dims.Z ? 0 : 90;
      }
      return { axis, offset };
    }

    function fitCameraToObject(object) {
      const box = new THREE.Box3().setFromObject(object);
      const size = box.getSize(new THREE.Vector3());
      const center = box.getCenter(new THREE.Vector3());
      const maxDim = Math.max(size.x, size.y, size.z);
      const distance = maxDim * 1.8;

      controls.target.copy(center);
      camera.position.copy(center);
      camera.position.z += distance;
      camera.position.y -= distance * 0.25;
      camera.near = distance / 100;
      camera.far = distance * 100;
      camera.updateProjectionMatrix();
      controls.update();
    }

    function updateBaseRotationFromInputs() {
      const axis = axisSelect.value || "Z";
      const offsetDeg = parseFloat(offsetInput.value) || 0;
      baseRotation.x = axis === "X" ? THREE.MathUtils.degToRad(offsetDeg) : 0;
      baseRotation.y = axis === "Y" ? THREE.MathUtils.degToRad(offsetDeg) : 0;
      baseRotation.z = axis === "Z" ? THREE.MathUtils.degToRad(offsetDeg) : 0;
      applyBaseRotation();
    }

    function updateBadgeSummary() {
      const qualityOption = qualitySelect.options[qualitySelect.selectedIndex];
      const qualityLabel = qualityOption ? qualityOption.textContent.trim() : qualitySelect.value;
      const offsetValue = Number(offsetInput.value) || 0;
      if (summaryQuality) {
        summaryQuality.textContent = `Quality • ${qualityLabel}`;
      }
      if (summaryOrientation) {
        summaryOrientation.textContent = autoCheckbox.checked ? "Auto orientation" : "Manual orientation";
      }
      if (summaryAxis) {
        summaryAxis.textContent = `Spin ${axisSelect.value || "Z"} • ${offsetValue.toFixed(0)}°`;
      }
    }

    function applyBaseRotation() {
      if (meshGroup) {
        meshGroup.rotation.set(baseRotation.x, baseRotation.y, baseRotation.z);
      }
      updateBadgeSummary();
    }

    async function loadPreview(file) {
      if (!file) {
        clearPreview();
        viewerNote.textContent = "Select an STL to preview.";
        currentDimensions = null;
        return;
      }
      const ext = file.name.split(".").pop().toLowerCase();
      if (ext !== "stl") {
        clearPreview();
        viewerNote.textContent = "Only STL previews are supported.";
        return;
      }
      viewerNote.textContent = "Loading preview…";
      const arrayBuffer = await file.arrayBuffer();

      clearPreview();
      try {
        const loader = new STLLoader();
        const geometry = loader.parse(arrayBuffer);
        geometry.computeVertexNormals();
        const mesh = new THREE.Mesh(geometry, createMaterial());
        meshGroup = new THREE.Group();
        meshGroup.add(mesh);
      } catch (error) {
        console.warn("Preview failed:", error);
        clearPreview();
        viewerNote.textContent =
          "Preview unavailable for this file, but rendering in Blender will still work.";
        currentDimensions = null;
        return;
      }

      scene.add(meshGroup);
      const box = new THREE.Box3().setFromObject(meshGroup);
      const size = box.getSize(new THREE.Vector3());
      currentDimensions = { X: size.x, Y: size.y, Z: size.z };
      resetViewButton.disabled = false;
      resetView();
      previewButton.disabled = !meshGroup;
      if (autoCheckbox.checked && currentDimensions) {
        const suggestion = computeAutoOrientation(currentDimensions);
        axisSelect.value = suggestion.axis;
        offsetInput.value = suggestion.offset.toFixed(0);
      }
      updateBaseRotationFromInputs();
      viewerNote.textContent = "Orbit with your mouse to inspect orientation. Preview spin shows the turntable look.";
      if (kelvinSelect) updatePreviewLighting(parseInt(kelvinSelect.value) || 5600);
      updatePreviewBrightness((!autoBrightnessCheckbox?.checked && exposureSlider) ? parseFloat(exposureSlider.value) || 0.0 : 0.0);
    }

    function resizeRenderer() {
      const parent = renderer.domElement.parentElement;
      if (!parent) return;
      const width = parent.clientWidth;
      const height = parent.clientHeight ? parent.clientHeight - 40 : 260;
      if (width && height) {
        renderer.setSize(width, height, false);
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
      }
    }

    function animate(now) {
      requestAnimationFrame(animate);
      if (previewState.active && meshGroup) {
        if (previewState.startTime === null) previewState.startTime = now;
        const progress = Math.min((now - previewState.startTime) / 1000 / previewState.duration, 1);
        const extra = progress * Math.PI * 2;
        const axis = axisSelect.value || "Z";
        meshGroup.rotation.set(baseRotation.x, baseRotation.y, baseRotation.z);
        meshGroup.rotation[axis.toLowerCase()] += extra;
        if (progress >= 1) {
          previewState.active = false;
          previewState.startTime = null;
          applyBaseRotation();
        }
      }
      controls.update();
      renderer.render(scene, camera);
    }
    requestAnimationFrame(animate);

    window.addEventListener("resize", resizeRenderer);
    resizeRenderer();

    function applyAutoState() {
      const autoOn = autoCheckbox.checked;
      axisSelect.disabled = autoOn;
      offsetInput.disabled = autoOn;
      if (autoOn && currentDimensions) {
        const suggestion = computeAutoOrientation(currentDimensions);
        axisSelect.value = suggestion.axis;
        offsetInput.value = suggestion.offset.toFixed(0);
      }
      updateBaseRotationFromInputs();
      updateBadgeSummary();
    }

    function resetView() {
      if (meshGroup) {
        fitCameraToObject(meshGroup);
        applyBaseRotation();
      } else {
        camera.position.copy(DEFAULT_CAMERA_POS);
        controls.target.copy(DEFAULT_CAMERA_TARGET);
        controls.update();
        updateBadgeSummary();
      }
    }

    fileInput.addEventListener("change", (e) => {
      try {
        const file = fileInput.files?.[0];
        loadPreview(file);
      } catch (error) {
        console.error("File input error:", error);
        uploadStatus.textContent = "Error loading file preview.";
      }
    });
    
    // Load preview if file is already selected when page loads (with delay to ensure DOM is ready)
    setTimeout(() => {
      try {
        if (fileInput && fileInput.files && fileInput.files.length > 0) {
          loadPreview(fileInput.files[0]);
        }
      } catch (error) {
        console.warn("Initial file load failed:", error);
      }
    }, 100);
    // Consolidated event listeners (optimized)
    axisSelect.addEventListener("change", () => {
      updateBaseRotationFromInputs();
      renderPreview();
    });
    offsetInput.addEventListener("input", () => {
      updateBaseRotationFromInputs();
      renderPreview();
    });
    qualitySelect.addEventListener("change", updateBadgeSummary);
    autoCheckbox.addEventListener("change", () => {
      applyAutoState();
    });
    
    // Brightness controls (optimized and consolidated)
    if (autoBrightnessCheckbox) {
      autoBrightnessCheckbox.addEventListener("change", () => {
        const autoOn = autoBrightnessCheckbox.checked;
        if (exposureField) exposureField.style.display = autoOn ? "none" : "block";
        if (exposureSlider) exposureSlider.disabled = autoOn;
        if (meshGroup) updatePreviewBrightness(autoOn ? 0.0 : (parseFloat(exposureSlider?.value) || 0.0));
      });
    }
    
    if (exposureSlider && exposureValue) {
      const brightnessIndicator = document.getElementById("brightness-indicator");
      const updateBrightnessMeter = (exposure) => {
        if (brightnessIndicator) brightnessIndicator.style.left = `${((exposure + 2) / 4) * 100}%`;
        if (exposureValue) exposureValue.textContent = exposure.toFixed(1);
      };
      updateBrightnessMeter(0);
      ["input", "change"].forEach(evt => exposureSlider.addEventListener(evt, () => {
        const exposure = parseFloat(exposureSlider.value);
        updateBrightnessMeter(exposure);
        updatePreviewBrightness(exposure);
      }));
    }
    
    previewButton.addEventListener("click", () => {
      if (!meshGroup || previewState.active) return;
      updateBaseRotationFromInputs();
      previewState.active = true;
      previewState.startTime = null;
    });
    resetViewButton.addEventListener("click", () => {
      if (!resetViewButton.disabled) {
        resetView();
      }
    });

    let pollTimer = null;
    let currentJobId = null;

    async function pollStatus() {
      if (!currentJobId) return;
      try {
        const resp = await fetch(`/status/${currentJobId}`);
        if (!resp.ok) {
          throw new Error("Failed to get status");
        }
        const data = await resp.json();
        if (data.message) {
          statusLabel.textContent = data.message;
        }
        if (typeof data.progress === "number") {
          const progressPercent = Math.max(0, Math.min(100, data.progress));
          progressBar.style.width = `${progressPercent}%`;
          
          // Show percentage instead of ETA
          if (totalEta && data.state === "running") {
            totalEta.textContent = `${Math.round(progressPercent)}% complete`;
            totalEta.style.display = "inline-block";
          } else if (totalEta) {
            totalEta.style.display = "none";
          }
        } else if (totalEta) {
          totalEta.style.display = "none";
        }
        if (data.state === "finished") {
          clearInterval(pollTimer);
          pollTimer = null;
          submitButton.disabled = false;
          if (cancelButton) cancelButton.classList.add("hidden");
          
      // Simplified: Always allow downloads (dev mode)
      if (downloadButton) {
        downloadButton.classList.remove("hidden");
        statusLabel.textContent = "Render complete! Click Download to save your video.";
        downloadButton.onclick = () => {
          window.location.href = `/download/${currentJobId}`;
        };
      }
        } else if (data.state === "cancelled") {
          clearInterval(pollTimer);
          pollTimer = null;
          showUploadView("Render cancelled.");
          statusLabel.textContent = "Render cancelled.";
        } else if (data.state === "error") {
          clearInterval(pollTimer);
          pollTimer = null;
          const errorMsg = data.message || "Rendering failed.";
          let userFriendlyMsg = errorMsg;
          if (errorMsg.includes("Blender") && errorMsg.includes("not found")) {
            userFriendlyMsg = "Blender is not installed or not found. Please install Blender and ensure it's in your PATH, or set the BLENDER_BIN environment variable.";
          } else if (errorMsg.includes("FFmpeg") || errorMsg.includes("ffmpeg")) {
            userFriendlyMsg = "Video processing failed. Please ensure FFmpeg is installed and available in your PATH.";
          } else if (errorMsg.includes("file") && errorMsg.includes("large")) {
            userFriendlyMsg = "File is too large. Maximum size is 512 MB. Please use a smaller STL file.";
          } else if (errorMsg.includes("STL") || errorMsg.includes("stl")) {
            userFriendlyMsg = "Invalid STL file. Please check that your file is a valid STL format and try again.";
          }
          showUploadView(userFriendlyMsg);
          statusLabel.textContent = userFriendlyMsg;
        }
      } catch (error) {
        clearInterval(pollTimer);
        pollTimer = null;
        showUploadView("Connection lost while polling progress.");
        statusLabel.textContent = "Connection lost while polling progress.";
      }
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
      statusLabel.textContent = "Uploading…";
      submitButton.disabled = true;
      progressBar.style.width = "0%";

      const formData = new FormData(form);
      formData.set("axis", axisSelect.value);
      formData.set("offset", offsetInput.value);
      formData.set("auto_orientation", autoCheckbox.checked ? "1" : "0");
      formData.set("quality", qualitySelect.value);
      const formatSelect = document.getElementById("format");
      const resolutionSelect = document.getElementById("resolution");
      if (formatSelect) formData.set("format", formatSelect.value);
      if (resolutionSelect) formData.set("resolution", resolutionSelect.value);

      try {
        const resp = await fetch("/render", {
          method: "POST",
          body: formData,
        });
        const payload = await resp.json();
        if (!resp.ok) {
          throw new Error(payload.message || "Upload failed.");
        }
        currentJobId = payload.job_id;
        showProgressView();
        statusLabel.textContent = "Rendering in Blender…";
        if (cancelButton) {
          cancelButton.classList.remove("hidden");
          cancelButton.onclick = async () => {
            if (!currentJobId) return;
            try {
              const resp = await fetch(`/cancel/${currentJobId}`, { method: "POST" });
              if (resp.ok) {
                clearInterval(pollTimer);
                pollTimer = null;
                showUploadView("Render cancelled.");
                statusLabel.textContent = "Render cancelled.";
                currentJobId = null;
              }
            } catch (error) {
              console.error("Failed to cancel:", error);
            }
          };
        }
        if (downloadButton) downloadButton.classList.add("hidden");
        pollTimer = setInterval(pollStatus, 1500);
      } catch (error) {
        showUploadView(error.message || "Upload failed.");
        statusLabel.textContent = error.message || "Upload failed.";
      }
    });

    autoCheckbox.checked = true;
    applyAutoState();
    // Status message comes from server template
    const initialStatus = statusLabel.textContent || "Ready when you are.";
    showUploadView(initialStatus);
    viewerNote.textContent = "Select an STL to preview.";