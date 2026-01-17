<template>
  <div class="container">
    <h1>Image Classification</h1>
    
    <div class="upload-section">
      <div class="file-input-wrapper">
        <input
          type="file"
          id="file-input"
          class="file-input"
          accept="image/*"
          @change="handleFileSelect"
          :disabled="loading"
        />
        <label for="file-input" class="file-label" :class="{ disabled: loading }">
          Choose Image
        </label>
      </div>
      
      <div v-if="selectedFile" class="file-name">
        Selected: {{ selectedFile.name }}
      </div>
      
      <div v-if="imagePreview" class="preview-container">
        <img :src="imagePreview" alt="Preview" class="preview-image" />
      </div>
      
      <button
        class="button"
        @click="classifyImage"
        :disabled="!selectedFile || loading"
      >
        Tell me what is on the image
      </button>
      
      <button
        v-if="showResumeButton"
        class="button resume-button"
        @click="retryTask"
        :disabled="!selectedFile || loading"
      >
        Resume
      </button>
      
      <div v-if="loading" class="loading">
        <span v-if="taskStatus === 'queued'">Image queued for processing...</span>
        <span v-else-if="taskStatus === 'processing'">Processing image...</span>
        <span v-else>Processing...</span>
      </div>
      
      <div v-if="error" class="error">
        {{ error }}
      </div>
    </div>
    
    <div v-if="results.length > 0" class="results-section">
      <h2>Classification Results</h2>
      <table class="results-table">
        <thead>
          <tr>
            <th>Label</th>
            <th>Probability</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(result, index) in results" :key="index">
            <td>{{ result.label }}</td>
            <td class="probability">{{ (result.probability * 100).toFixed(2) }}%</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
import { ref, computed, onUnmounted } from 'vue'

export default {
  name: 'App',
  setup() {
    const selectedFile = ref(null)
    const imagePreview = ref(null)
    const results = ref([])
    const loading = ref(false)
    const error = ref(null)
    const taskId = ref(null)
    const taskStatus = ref(null)
    const pollInterval = ref(null)
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'

    const showResumeButton = computed(() => {
      return taskStatus.value === 'failed' && selectedFile.value
    })

    const handleFileSelect = (event) => {
      const file = event.target.files[0]
      if (file) {
        selectedFile.value = file
        
        // Create preview
        const reader = new FileReader()
        reader.onload = (e) => {
          imagePreview.value = e.target.result
        }
        reader.readAsDataURL(file)
        
        // Reset previous results and error
        results.value = []
        error.value = null
        taskId.value = null
        taskStatus.value = null
        stopPolling()
      }
    }

    const stopPolling = () => {
      if (pollInterval.value) {
        clearInterval(pollInterval.value)
        pollInterval.value = null
      }
    }

    const pollTaskStatus = async () => {
      if (!taskId.value) return

      try {
        const response = await fetch(`${apiUrl}/task/${taskId.value}/status`)
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const data = await response.json()
        taskStatus.value = data.status

        if (data.status === 'completed') {
          stopPolling()
          loading.value = false
          results.value = data.results || []
          error.value = null
        } else if (data.status === 'failed') {
          stopPolling()
          loading.value = false
          error.value = data.error || 'Classification failed. Please try again.'
          results.value = []
        }
        // Continue polling for 'queued' and 'processing' statuses
      } catch (err) {
        console.error('Error polling task status:', err)
        // Don't stop polling on network errors, might be temporary
      }
    }

    const classifyImage = async () => {
      if (!selectedFile.value) return

      loading.value = true
      error.value = null
      results.value = []
      taskStatus.value = null
      stopPolling()

      try {
        const formData = new FormData()
        formData.append('file', selectedFile.value)

        const response = await fetch(`${apiUrl}/classify`, {
          method: 'POST',
          body: formData
        })

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP error! status: ${response.status}`)
        }

        const data = await response.json()
        taskId.value = data.task_id
        taskStatus.value = data.status

        // Start polling for task status
        pollTaskStatus()
        pollInterval.value = setInterval(pollTaskStatus, 1000) // Poll every second
      } catch (err) {
        loading.value = false
        error.value = `Error: ${err.message}. Make sure the backend is running on ${apiUrl}`
        console.error('Error classifying image:', err)
        stopPolling()
      }
    }

    const retryTask = async () => {
      if (!selectedFile.value || !taskId.value) return

      loading.value = true
      error.value = null
      results.value = []
      stopPolling()

      try {
        const formData = new FormData()
        formData.append('file', selectedFile.value)

        const response = await fetch(`${apiUrl}/task/${taskId.value}/retry`, {
          method: 'POST',
          body: formData
        })

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP error! status: ${response.status}`)
        }

        const data = await response.json()
        taskStatus.value = data.status

        // Start polling for task status
        pollTaskStatus()
        pollInterval.value = setInterval(pollTaskStatus, 1000)
      } catch (err) {
        loading.value = false
        error.value = `Error retrying: ${err.message}`
        console.error('Error retrying task:', err)
        stopPolling()
      }
    }

    // Cleanup polling on component unmount
    onUnmounted(() => {
      stopPolling()
    })

    return {
      selectedFile,
      imagePreview,
      results,
      loading,
      error,
      taskStatus,
      showResumeButton,
      handleFileSelect,
      classifyImage,
      retryTask
    }
  }
}
</script>
