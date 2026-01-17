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
        />
        <label for="file-input" class="file-label">
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
      
      <div v-if="loading" class="loading">
        Processing image...
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
import { ref } from 'vue'

export default {
  name: 'App',
  setup() {
    const selectedFile = ref(null)
    const imagePreview = ref(null)
    const results = ref([])
    const loading = ref(false)
    const error = ref(null)

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
      }
    }

    const classifyImage = async () => {
      if (!selectedFile.value) return

      loading.value = true
      error.value = null
      results.value = []

      try {
        const formData = new FormData()
        formData.append('file', selectedFile.value)

        const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
        const response = await fetch(`${apiUrl}/classify`, {
          method: 'POST',
          body: formData
        })

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const data = await response.json()
        results.value = data.results || []
      } catch (err) {
        error.value = `Error: ${err.message}. Make sure the backend is running on http://localhost:8000`
        console.error('Error classifying image:', err)
      } finally {
        loading.value = false
      }
    }

    return {
      selectedFile,
      imagePreview,
      results,
      loading,
      error,
      handleFileSelect,
      classifyImage
    }
  }
}
</script>
