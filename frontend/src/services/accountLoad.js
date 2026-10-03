export async function resolveAccountLoad(userId, { getUser, getFinancialProfile }) {
  try {
    const user = await getUser(userId)
    let profile
    try {
      profile = await getFinancialProfile(userId)
    } catch (error) {
      if (error.response?.status !== 404) throw error
      profile = null
    }
    return { status: 'ready', user, profile }
  } catch (error) {
    return { status: 'error', error }
  }
}
