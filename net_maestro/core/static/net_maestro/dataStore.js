document.addEventListener('alpine:init', () => {
    Alpine.store('dataStore', {
        rossData: null,
        loading: false,

        async loadRossData() {
            if(this.loading || this.rossData){
                return
            }
            this.loading = true
            try {
                const response = await fetch('api/v1/data/ross')
                const data = await response.json()

                this.rossData = data
            } catch (error) {
                throw error;
            } finally {
                this.loading = false
            }

        }
    })
})
