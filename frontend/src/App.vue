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
    const eventSource = ref(null)
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
        stopEventStream()
      }
    }

    const stopEventStream = () => {
      if (eventSource.value) {
        eventSource.value.close()
        eventSource.value = null
      }
    }

    const startEventStream = (taskId) => {
      stopEventStream()
      
      const streamUrl = `${apiUrl}/task/${taskId}/stream`
      eventSource.value = new EventSource(streamUrl)
      
      eventSource.value.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          taskStatus.value = data.status
          
          if (data.status === 'completed') {
            stopEventStream()
            loading.value = false
            results.value = data.results || []
            error.value = null
          } else if (data.status === 'failed') {
            stopEventStream()
            loading.value = false
            error.value = data.error || 'Classification failed. Please try again.'
            results.value = []
          }
        } catch (err) {
          console.error('Error parsing SSE message:', err)
        }
      }
      
      eventSource.value.onerror = (err) => {
        console.error('SSE connection error:', err)
        // Keep connection open, might recover
      }
    }

    const classifyImage = async () => {
      if (!selectedFile.value) return

      loading.value = true
      error.value = null
      results.value = []
      taskStatus.value = null
      stopEventStream()

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

        // Start SSE stream for real-time updates
        startEventStream(data.task_id)
      } catch (err) {
        loading.value = false
        error.value = `Error: ${err.message}. Make sure the backend is running on ${apiUrl}`
        console.error('Error classifying image:', err)
        stopEventStream()
      }
    }

    const retryTask = async () => {
      if (!selectedFile.value || !taskId.value) return

      loading.value = true
      error.value = null
      results.value = []
      stopEventStream()

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

        // Start SSE stream for real-time updates
        startEventStream(taskId.value)
      } catch (err) {
        loading.value = false
        error.value = `Error retrying: ${err.message}`
        console.error('Error retrying task:', err)
        stopEventStream()
      }
    }

    // Cleanup event stream on component unmount
    onUnmounted(() => {
      stopEventStream()
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
