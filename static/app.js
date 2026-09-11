const { createApp, computed, onMounted, ref } = Vue;

createApp({
    setup() {
        const view = ref("loading");
        const loading = ref(true);
        const submitting = ref(false);
        const error = ref("");
        const profileOpen = ref(false);
        const profileModal = ref(false);
        const profileForm = ref({
            nickname: "", bio: "", gender: "", birthday: "",
            country: "", region: "", signature: "",
        });
        const profilePreview = ref("");
        const profileFile = ref(null);
        const profileSaving = ref(false);
        const profileError = ref("");
        const profileCloseConfirm = ref(false);
        const scanOpen = ref(false);
        const activeNav = ref("home");
        const dashboard = ref(null);
        const exerciseGuides = ref([]);
        const exerciseLogs = ref([]);
        const exerciseError = ref("");
        const exerciseSaving = ref(false);
        const exerciseHistoryAll = ref(false);
        const exerciseFilterDate = ref("");
        const exerciseFilterType = ref("");
        const exerciseForm = ref({ exercise_type: "", duration_minutes: null, energy_kcal: null });
        const communityPosts = ref([]);
        const communityContent = ref("");
        const communityError = ref("");
        const communitySaving = ref(false);
        const communityComments = ref({});
        const communityDrafts = ref({});
        const communityCommentOpen = ref({});
        const communityProfile = ref(null);
        const credentials = ref({ email: "admin", password: "123" });
        const navItems = [
            { key: "home", label: "首页", icon: "⌂", description: "综合健康概览" },
            { key: "exercise", label: "运动", icon: "↗", description: "记录与训练指导" },
            { key: "community", label: "运动社区", icon: "✚", description: "分享训练与健康生活" },
            { key: "health", label: "健康", icon: "♡", description: "指标监测与评估" },
            { key: "plan", label: "处方/方案", icon: "✦", description: "个性化健康干预" },
            { key: "profile", label: "我的", icon: "○", description: "账户与设备管理" },
        ];

        const isDashboard = computed(() => view.value === "dashboard");
        const formattedUser = computed(() => dashboard.value?.user?.name || "Yun");
        const avatarLetter = computed(() => (formattedUser.value || "Y").charAt(0).toUpperCase());
        const selectedExerciseGuide = computed(() => exerciseGuides.value.find((item) => item.key === exerciseForm.value.exercise_type));
        const exerciseTotalMinutes = computed(() => exerciseLogs.value.reduce((total, log) => total + Number(log.duration_minutes || 0), 0));

        async function request(url, options = {}) {
            const isFormData = options.body instanceof FormData;
            const response = await fetch(url, {
                headers: isFormData ? (options.headers || {}) : { "Content-Type": "application/json", ...(options.headers || {}) },
                ...options,
            });
            const responseText = await response.text();
            let data;
            try {
                data = responseText ? JSON.parse(responseText) : {};
            } catch (parseError) {
                throw new Error(response.ok ? "服务器返回了无效响应" : `服务器错误（${response.status}），请查看后端日志`);
            }
            if (!response.ok) {
                throw new Error(data.message || "请求失败，请稍后再试");
            }
            return data;
        }

        async function loadDashboard() {
            dashboard.value = await request("/api/dashboard");
            view.value = "dashboard";
        }

        async function loadExercises(showAll = exerciseHistoryAll.value) {
            const params = new URLSearchParams();
            if (showAll) params.set("all", "1");
            if (exerciseFilterDate.value) params.set("date", exerciseFilterDate.value);
            if (exerciseFilterType.value) params.set("exercise_type", exerciseFilterType.value);
            const query = params.toString();
            const result = await request(`/api/exercises${query ? `?${query}` : ""}`);
            exerciseGuides.value = result.guides;
            exerciseLogs.value = result.logs;
        }

        async function loadCommunity() {
            const result = await request("/api/community/posts");
            communityPosts.value = result.posts;
        }

        async function openCommunityProfile(userId) {
            communityError.value = "";
            try {
                communityProfile.value = await request(`/api/community/users/${userId}`);
            } catch (requestError) {
                communityError.value = requestError.message;
            }
        }

        function closeCommunityProfile() {
            communityProfile.value = null;
        }

        async function toggleCommunityFollow() {
            const user = communityProfile.value?.user;
            if (!user) return;
            try {
                const result = await request(`/api/community/users/${user.id}/follow`, { method: "POST" });
                user.following = result.following;
                user.followers_count = result.followers_count;
            } catch (requestError) {
                communityError.value = requestError.message;
            }
        }

        async function selectCommunityNav() {
            activeNav.value = "community";
            communityError.value = "";
            try {
                await loadCommunity();
            } catch (requestError) {
                communityError.value = requestError.message;
            }
        }

        async function createCommunityPost() {
            const content = communityContent.value.trim();
            if (!content) {
                communityError.value = "请先写下你想分享的内容";
                return;
            }
            communitySaving.value = true;
            communityError.value = "";
            try {
                await request("/api/community/posts", {
                    method: "POST",
                    body: JSON.stringify({ content }),
                });
                communityContent.value = "";
                await loadCommunity();
            } catch (requestError) {
                communityError.value = requestError.message;
            } finally {
                communitySaving.value = false;
            }
        }

        async function toggleCommunityLike(post) {
            try {
                const result = await request(`/api/community/posts/${post.id}/like`, { method: "POST" });
                post.liked = result.liked;
                post.like_count = result.like_count;
            } catch (requestError) {
                communityError.value = requestError.message;
            }
        }

        async function toggleCommunityComments(post) {
            communityCommentOpen.value[post.id] = !communityCommentOpen.value[post.id];
            if (communityCommentOpen.value[post.id] && !communityComments.value[post.id]) {
                try {
                    const result = await request(`/api/community/posts/${post.id}/comments`);
                    communityComments.value[post.id] = result.comments;
                } catch (requestError) {
                    communityError.value = requestError.message;
                }
            }
        }

        async function createCommunityComment(post) {
            const content = (communityDrafts.value[post.id] || "").trim();
            if (!content) return;
            try {
                await request(`/api/community/posts/${post.id}/comments`, {
                    method: "POST",
                    body: JSON.stringify({ content }),
                });
                communityDrafts.value[post.id] = "";
                const result = await request(`/api/community/posts/${post.id}/comments`);
                communityComments.value[post.id] = result.comments;
                post.comment_count = result.comments.length;
            } catch (requestError) {
                communityError.value = requestError.message;
            }
        }

        async function filterExerciseHistory() {
            exerciseHistoryAll.value = true;
            exerciseError.value = "";
            try {
                await loadExercises(true);
            } catch (requestError) {
                exerciseError.value = requestError.message;
            }
        }

        async function clearExerciseFilters() {
            exerciseFilterDate.value = "";
            exerciseFilterType.value = "";
            await filterExerciseHistory();
        }

        async function toggleExerciseHistory() {
            exerciseHistoryAll.value = !exerciseHistoryAll.value;
            exerciseError.value = "";
            try {
                await loadExercises();
            } catch (requestError) {
                exerciseError.value = requestError.message;
            }
        }

        async function selectNav(key) {
            if (key === "community") {
                await selectCommunityNav();
                return;
            }
            activeNav.value = key;
            if (key === "exercise" && !exerciseGuides.value.length) {
                try {
                    await loadExercises();
                } catch (requestError) {
                    exerciseError.value = requestError.message;
                }
            }
        }

        function exerciseName(key) {
            return exerciseGuides.value.find((item) => item.key === key)?.name || key;
        }

        async function saveExercise() {
            exerciseSaving.value = true;
            exerciseError.value = "";
            try {
                await request("/api/exercises/log", {
                    method: "POST",
                    body: JSON.stringify(exerciseForm.value),
                });
                await loadExercises();
                await loadDashboard();
                activeNav.value = "exercise";
                exerciseForm.value.duration_minutes = null;
                exerciseForm.value.energy_kcal = null;
            } catch (requestError) {
                exerciseError.value = requestError.message;
            } finally {
                exerciseSaving.value = false;
            }
        }

        async function initialize() {
            try {
                const oauthError = new URLSearchParams(window.location.search).get("oauth_error");
                if (oauthError) error.value = oauthError;
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

        function oauthLogin(provider) {
            window.location.href = `/auth/${provider}`;
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
            profileCloseConfirm.value = false;
            profileForm.value = {
                nickname: dashboard.value.user.nickname || dashboard.value.user.name || "",
                bio: dashboard.value.user.bio || "",
                gender: dashboard.value.user.gender || "",
                birthday: dashboard.value.user.birthday || "",
                country: dashboard.value.user.country || "",
                region: dashboard.value.user.region || "",
                signature: dashboard.value.user.signature || "",
            };
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

        function closeProfile() {
            profileModal.value = false;
            profileCloseConfirm.value = false;
            profileFile.value = null;
        }

        function cancelProfileEdit() {
            closeProfile();
        }

        function requestCloseProfile() {
            if (!profileSaving.value) profileCloseConfirm.value = true;
        }

        function continueProfileEdit() {
            profileCloseConfirm.value = false;
        }

        function discardProfileChanges() {
            closeProfile();
        }

        async function saveProfile() {
            profileSaving.value = true;
            profileError.value = "";
            try {
                const formData = new FormData();
                Object.entries(profileForm.value).forEach(([key, value]) => {
                    formData.append(key, value.trim());
                });
                if (profileFile.value) formData.append("avatar", profileFile.value);
                const result = await request("/api/profile", { method: "PUT", body: formData });
                dashboard.value.user = result.user;
                profileModal.value = false;
                profileCloseConfirm.value = false;
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
            selectNav,
            navItems,
            dashboard,
            exerciseGuides,
            exerciseLogs,
            exerciseForm,
            exerciseError,
            exerciseSaving,
            exerciseHistoryAll,
            exerciseFilterDate,
            exerciseFilterType,
            selectedExerciseGuide,
            exerciseTotalMinutes,
            exerciseName,
            communityPosts,
            communityContent,
            communityError,
            communitySaving,
            communityComments,
            communityDrafts,
            communityCommentOpen,
            communityProfile,
            credentials,
            isDashboard,
            formattedUser,
            avatarLetter,
            profileModal,
            profileForm,
            profilePreview,
            profileSaving,
            profileError,
            profileCloseConfirm,
            login,
            oauthLogin,
            logout,
            syncSteps,
            goAdmin,
            openProfile,
            selectAvatar,
            requestCloseProfile,
            cancelProfileEdit,
            continueProfileEdit,
            discardProfileChanges,
            saveProfile,
            saveExercise,
            toggleCommunityLike,
            toggleCommunityComments,
            createCommunityPost,
            createCommunityComment,
            openCommunityProfile,
            closeCommunityProfile,
            toggleCommunityFollow,
            toggleExerciseHistory,
            filterExerciseHistory,
            clearExerciseFilters,
        };
    },
}).mount("#app");
