import { startTransition, useState } from "react"

import type { Screen } from "./types"

export function useScreenStack(initialScreen: Screen) {
  const [screenStack, setScreenStack] = useState<Screen[]>([initialScreen])
  const currentScreen = screenStack.at(-1) ?? initialScreen

  function pushScreen(screen: Screen) {
    startTransition(() => {
      setScreenStack((current) => [...current, screen])
    })
  }

  function resetToScreen(screen: Screen) {
    startTransition(() => {
      setScreenStack([screen])
    })
  }

  function popScreen() {
    startTransition(() => {
      setScreenStack((current) => (current.length > 1 ? current.slice(0, -1) : current))
    })
  }

  function replaceCurrentScreen(screen: Screen) {
    startTransition(() => {
      setScreenStack((current) => [...current.slice(0, -1), screen])
    })
  }

  return {
    currentScreen,
    popScreen,
    pushScreen,
    replaceCurrentScreen,
    resetToScreen,
  }
}
