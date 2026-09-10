const { createApp, computed, onMounted, ref } = Vue;

createApp({
    setup() {
        const view = ref("loading");
        const loading = ref(true);
        const submitting = ref(false);
        const error = ref("");
        const profileOpen = ref(false);
        const profileModal = ref(false);
        const profileName = ref("");
        const profilePreview = ref("");
        const profileFile = ref(null);
        const profileSaving = ref(false);
        const profileError = ref("");
        const scanOpen = ref(false);
        const activeNav = ref("home");
        const dashboard = ref(null);
        const credentials = ref({ email: "admin", password: "123" });
        const navItems = [
            { key: "home", label: "首页", icon: "⌂", description: "综合健康概览" },
            { key: "exercise", label: "运动", icon: "↗", description: "记录与训练指导" },
            { key: "health", label: "健康", icon: "♡", description: "指标监测与评估" },
            { key: "plan", label: "处方/方案", icon: "✦", description: "个性化健康干预" },
            { key: "profile", label: "我的", icon: "○", description: "账户与设备管理" },
        ];

        const isDashboard = computed(() => view.value === "dashboard");
        const formattedUser = computed(() => dashboard.value?.user?.name || "Yun");
        const avatarLetter = computed(() => (formattedUser.value || "Y").charAt(0).toUpperCase());

        async function request(url, options = {}) {
            const isFormData = options.body instanceof FormData;
            const response = await fetch(url, {
                headers: isFormData ? (options.headers || {}) : { "Content-Type": "application/json", ...(options.headers || {}) },
                ...options,
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.message || "请求失败，请稍后再试");
            }
            return data;
        }

        async function loadDashboard() {
            dashboard.value = await request("/api/dashboard");
            view.value = "dashboard";
        }

        async function initialize() {
            try {
                const auth = await request("/api/auth");
                if (auth.authenticated) {
                    await loadDashboard();
                } else {
                    view.value = "login";
                }
            } catch (requestError) {
                error.value = requestError.message;
                view.value = "login";
            } finally {
                loading.value = false;
            }
        }

        async function login() {
            error.value = "";
            submitting.value = true;
            try {
                await request("/api/login", {
                    method: "POST",
                    body: JSON.stringify(credentials.value),
                });
                await loadDashboard();
            } catch (requestError) {
                error.value = requestError.message;
            } finally {
                submitting.value = false;
            }
        }

        async function logout() {
            await request("/api/logout", { method: "POST" });
            profileOpen.value = false;
            dashboard.value = null;
            view.value = "login";
        }

        async function syncSteps() {
            try {
                const result = await request("/api/sync-steps", { method: "POST" });
                const metric = dashboard.value.metrics.find((item) => item.key === "steps");
                if (metric) metric.value = result.steps;
                dashboard.value.hero.steps = result.steps;
            } catch (requestError) {
                error.value = requestError.message;
            }
        }

        function goAdmin() {
            window.location.href = "/admin";
        }

        function openProfile() {
            profileOpen.value = false;
            profileError.value = "";
            profileName.value = dashboard.value.user.name || "";
            profilePreview.value = dashboard.value.user.avatar || "";
            profileFile.value = null;
            profileModal.value = true;
        }

        function selectAvatar(event) {
            const file = event.target.files[0];
            if (!file) return;
            if (file.size > 2 * 1024 * 1024) {
                profileError.value = "头像图片不能超过 2MB";
                return;
            }
            profileFile.value = file;
            profilePreview.value = URL.createObjectURL(file);
            profileError.value = "";
        }

        async function saveProfile() {
            profileSaving.value = true;
            profileError.value = "";
            try {
                const formData = new FormData();
                formData.append("name", profileName.value.trim());
                if (profileFile.value) formData.append("avatar", profileFile.value);
                const result = await request("/api/profile", { method: "PUT", body: formData });
                dashboard.value.user = result.user;
                profileModal.value = false;
            } catch (requestError) {
                profileError.value = requestError.message;
            } finally {
                profileSaving.value = false;
            }
        }

        onMounted(initialize);

        return {
            view,
            loading,
            submitting,
            error,
            profileOpen,
            scanOpen,
            activeNav,
            navItems,
            dashboard,
            credentials,
            isDashboard,
            formattedUser,
            avatarLetter,
            profileModal,
            profileName,
            profilePreview,
            profileSaving,
            profileError,
            login,
            logout,
            syncSteps,
            goAdmin,
            openProfile,
            selectAvatar,
            saveProfile,
        };
    },
}).mount("#app");
