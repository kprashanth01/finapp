export function getDashboardDisplayState({ saving = false, analysis = null, advisoryLoading = false, advisoryError = '', advisorySession = null }) {
  return {
    updating: saving,
    snapshot: analysis ? 'ready' : 'unavailable',
    latest: advisoryLoading ? 'loading' : advisoryError ? 'error' : advisorySession ? 'saved' : 'empty',
  }
}
