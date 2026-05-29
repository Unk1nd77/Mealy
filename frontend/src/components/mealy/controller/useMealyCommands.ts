import type { FormEvent } from "react";

import { useI18n } from "../i18n";
import { extractBearerToken } from "../api";
import {
  createMealyClient,
  formToUserPayload,
  profileToUserPayload,
} from "../client";
import { clamp } from "../formatters";
import { patchStoredSession } from "../session";
import { registerOrCreateUser } from "./authFlow";
import { createMealCommands } from "./mealCommands";
import { createPlanUtilityCommands } from "./planUtilityCommands";
import type { useMealyController } from "./useMealyController";

export type MealyCore = ReturnType<typeof useMealyController>;
export type MealyCommands = ReturnType<typeof useMealyCommands>;

export function useMealyCommands(core: MealyCore) {
  const { t } = useI18n();
  function goToNextStep() {
    const error = validateStep();
    if (error) return core.patch({ errorNotice: error });
    core.patch({
      errorNotice: "",
      onboardingStep: clamp(core.onboardingStep + 1, 1, core.onboardingSteps),
    });
  }

  function goToPreviousStep() {
    core.patch({
      errorNotice: "",
      onboardingStep: clamp(core.onboardingStep - 1, 1, core.onboardingSteps),
    });
  }

  function validateStep() {
    if (core.onboardingStep === 1) {
      if (
        !core.onboardingForm.email.trim() ||
        !core.onboardingForm.password.trim()
      ) {
        return core.authMode === "login"
          ? t("error.signInRequired")
          : t("error.registerRequired");
      }
      if (core.onboardingForm.password.trim().length < 6) {
        return t("error.passwordLength");
      }
    }
    if (core.authMode === "login") return null;
    if (
      core.onboardingStep === 2 &&
      (!core.onboardingForm.age ||
        !core.onboardingForm.weight_kg ||
        !core.onboardingForm.height_cm)
    ) {
      return t("error.bodyMetrics");
    }
    return null;
  }

  async function loginExistingUser(event: FormEvent) {
    event.preventDefault();
    core.patch({ errorNotice: "", globalNotice: "", isWorking: true });
    try {
      const auth = await core.client.login(
        core.onboardingForm.email,
        core.onboardingForm.password,
      );
      const token = extractBearerToken(auth);
      const userId = auth.user?.id ?? auth.user_id;
      if (!token || !userId)
        throw new Error("Login succeeded without a usable session.");
      const user = auth.user ?? (await createMealyClient(token).authMe());
      core.setAccessToken(token);
      core.patch({ user, globalNotice: t("notice.signedIn") });
      patchStoredSession({
        userId,
        accessToken: token,
        planId: undefined,
        taskId: undefined,
      });
      core.resetToScreen({ name: "home" });
    } catch (error) {
      core.patch({
        errorNotice:
          error instanceof Error ? error.message : t("error.signInFailed"),
      });
    } finally {
      core.patch({ isWorking: false });
    }
  }

  async function createUserAndGenerate(event: FormEvent) {
    event.preventDefault();
    core.patch({ errorNotice: "", globalNotice: "", isWorking: true });
    try {
      const tokenBeforeGenerate = core.accessToken;
      const { user, token } = await registerOrCreateUser({
        client: core.client,
        fallbackPassword: core.onboardingForm.password,
        payload: formToUserPayload(core.onboardingForm),
      });
      core.patch({ user });
      if (token) core.setAccessToken(token);
      patchStoredSession({ userId: user.id, accessToken: token ?? undefined });
      core.resetToScreen({ name: "generating" });
      const runToken = token ?? tokenBeforeGenerate;
      const client = createMealyClient(runToken);
      const { task_id } = await client.generatePlan(user.id);
      patchStoredSession({
        userId: user.id,
        taskId: task_id,
        planId: undefined,
      });
      await core.monitorTask(task_id, user.id, runToken);
    } catch (error) {
      core.patch({
        errorNotice:
          error instanceof Error
            ? error.message
            : "Could not start onboarding.",
      });
      core.resetToScreen({ name: "onboarding" });
    } finally {
      core.patch({ isWorking: false });
    }
  }

  async function regenerateWeek() {
    if (!core.user) return;
    core.patch({
      errorNotice: "",
      globalNotice: "",
      generationStatus: "PENDING",
      generationError: "",
    });
    core.resetToScreen({ name: "generating" });
    try {
      const { task_id } = await core.client.generatePlan(core.user.id);
      patchStoredSession({
        userId: core.user.id,
        taskId: task_id,
        planId: undefined,
      });
      await core.monitorTask(task_id, core.user.id, core.accessToken);
    } catch (error) {
      core.patch({
        generationError:
          error instanceof Error
            ? error.message
            : "Could not refresh your week.",
      });
    }
  }

  async function saveProfile() {
    if (!core.user) return;
    core.patch({ isSavingProfile: true, errorNotice: "", globalNotice: "" });
    if (!core.accessToken) {
      core.patch({
        errorNotice: t("notice.sessionExpired"),
        isSavingProfile: false,
      });
      return;
    }
    try {
      const payload = profileToUserPayload(core.profileDraft);
      const user = await core.client.updateMe(payload);
      core.patch({
        user,
        globalNotice: "Preferences saved. Generate a fresh week to apply them.",
      });
    } catch (error) {
      core.patch({
        errorNotice:
          error instanceof Error ? error.message : "Could not save profile.",
      });
    } finally {
      core.patch({ isSavingProfile: false });
    }
  }

  const mealCommands = createMealCommands(core);
  const planUtilityCommands = createPlanUtilityCommands(core);

  return {
    createUserAndGenerate,
    goToNextStep,
    goToPreviousStep,
    loginExistingUser,
    regenerateWeek,
    saveProfile,
    ...mealCommands,
    ...planUtilityCommands,
  };
}
