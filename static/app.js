const { createApp, computed, onMounted, ref } = Vue;

createApp({
    setup() {
        const view = ref("loading");
        const loading = ref(true);
        const submitting = ref(false);
        const error = ref("");
        const profileOpen = ref(false);
        const profileModal = ref(false);
        const settingsOpen = ref(false);
        const securityOpen = ref(false);
        const settingsPage = ref("root");
        const darkMode = ref(localStorage.getItem("movewell-dark-mode") === "1");
        const displayMode = ref(localStorage.getItem("movewell-display-mode") || "normal");
        const fontScale = ref(localStorage.getItem("movewell-font-scale") || "normal");
        const notificationSettings = ref(JSON.parse(localStorage.getItem("movewell-notifications") || '{"system":true,"preview":true,"calls":true,"quick":true,"banner":true,"sound":true,"vibration":true,"dnd":false,"birthday":false,"groups":true}'));
        const privacySettings = ref(JSON.parse(localStorage.getItem("movewell-privacy") || '{"strangerInvite":false,"strangerLike":true,"online":true}'));
        const passwordForm = ref({ current_password: "", new_password: "", confirm_password: "" });
        const passwordSaving = ref(false);
        const passwordError = ref("");
        const passwordSuccess = ref("");
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
        const privateMessageUser = ref(null);
        const privateMessageDraft = ref("");
        const privateMessages = ref([]);
        const privateMessageLoading = ref(false);
        const privateMessageSending = ref(false);
        const privateMessageError = ref("");
        const privateMessageReply = ref(null);
        const privateImageFile = ref(null);
        const privateImagePreview = ref("");
        const privateEmojiOpen = ref(false);
        const privateEmojis = ["😀", "😂", "😍", "🥳", "👍", "👏", "❤️", "🎉", "😅", "🤔", "🙏", "💪"];
        const socialCenterOpen = ref(false);
        const socialTab = ref("followers");
        const socialLoading = ref(false);
        const socialError = ref("");
        const socialData = ref({ followers: [], conversations: [], notifications: [] });
        const socialUnread = ref({ followers: 0, messages: 0, notifications: 0 });
        const credentials = ref({ email: "admin", password: "123" });
        const mentalMood = ref(localStorage.getItem("movewell-mental-mood") || "");
        const mentalCheckinSaved = ref(Boolean(localStorage.getItem("movewell-mental-checkin")));
        const mentalMoods = [
            { key: "calm", label: "平静", icon: "☁", note: "状态稳定" },
            { key: "good", label: "不错", icon: "☀", note: "有精力应对今天" },
            { key: "tired", label: "疲惫", icon: "◔", note: "需要一点恢复" },
            { key: "anxious", label: "焦虑", icon: "≈", note: "思绪有些紧绷" },
            { key: "low", label: "低落", icon: "◡", note: "今天对自己温柔些" },
        ];
        const planVersion = ref(0);
        const planItems = computed(() => {
            const sleep = Number(dashboard.value?.metrics?.find((item) => item.key === "sleep")?.value || 0);
            const water = Number(dashboard.value?.metrics?.find((item) => item.key === "water")?.value || 0);
            const exercise = Number(dashboard.value?.hero?.exerciseMinutes || 0);
            return [
                { key: "move", icon: "↗", title: exercise >= 30 ? "保持轻量活动" : "完成 20 分钟活动", detail: exercise >= 30 ? "今天已有运动记录，做 5 分钟拉伸即可。" : "选择快走、瑜伽或骑行，保持可以交谈的强度。", tag: "运动" },
                { key: "water", icon: "◌", title: water >= 2.2 ? "维持补水节奏" : "补充一杯水", detail: water >= 2.2 ? "今日饮水已达到建议目标，继续少量多次。" : `目前约 ${water}L，分时段补足至 2.2L。`, tag: "补水" },
                { key: "sleep", icon: "☾", title: sleep >= 7 ? "保护今晚睡眠" : "今晚提前 30 分钟休息", detail: sleep >= 7 ? "保持固定入睡时间，睡前减少屏幕刺激。" : "睡前一小时放下工作，给身体留出恢复时间。", tag: "睡眠" },
                { key: "recovery", icon: "♡", title: "安排 10 分钟恢复", detail: "做肩颈放松、呼吸练习或安静散步，不追求强度。", tag: "恢复" },
                { key: "reflection", icon: "✦", title: "记录一个小进展", detail: "写下今天完成的一件事，帮助自己看见持续的变化。", tag: "觉察" },
            ];
        });
        const planCompletedCount = computed(() => {
            planVersion.value;
            return planItems.value.filter((item) => isPlanItemDone(item.key)).length;
        });
        const planProgress = computed(() => Math.round(planCompletedCount.value / planItems.value.length * 100));

        if (darkMode.value) document.body.classList.add("dark-mode");
        if (displayMode.value === "care") document.body.classList.add("care-mode");
        if (fontScale.value === "large") document.body.classList.add("large-text-mode");
        const navItems = [
            { key: "home", label: "首页", icon: "⌂", description: "综合健康概览" },
            { key: "exercise", label: "运动", icon: "↗", description: "记录与训练指导" },
            { key: "community", label: "运动社区", icon: "✚", description: "分享训练与健康生活" },
            { key: "health", label: "心理健康", icon: "♡", description: "指标监测与评估" },
            { key: "plan", label: "处方/方案", icon: "✦", description: "个性化健康干预" },
            { key: "profile", label: "我的", icon: "○", description: "账户与设备管理" },
        ];

        const isDashboard = computed(() => view.value === "dashboard");
        const formattedUser = computed(() => dashboard.value?.user?.name || "Yun");
        const avatarLetter = computed(() => (formattedUser.value || "Y").charAt(0).toUpperCase());
        const selectedExerciseGuide = computed(() => exerciseGuides.value.find((item) => item.key === exerciseForm.value.exercise_type));
        const exerciseTotalMinutes = computed(() => exerciseLogs.value.reduce((total, log) => total + Number(log.duration_minutes || 0), 0));
        const mentalRecoveryScore = computed(() => {
            const sleepQuality = Number(dashboard.value?.hero?.sleepQuality || 0);
            const sleepMetric = dashboard.value?.metrics?.find((item) => item.key === "sleep");
            const sleepHours = Number(sleepMetric?.value || 0);
            return Math.max(0, Math.min(100, Math.round(sleepQuality * 0.7 + Math.min(sleepHours / 8, 1) * 30)));
        });
        const mentalStatus = computed(() => {
            if (mentalRecoveryScore.value >= 78) return { label: "恢复状态良好", tone: "good" };
            if (mentalRecoveryScore.value >= 55) return { label: "需要适度调整", tone: "steady" };
            return { label: "优先安排恢复", tone: "attention" };
        });
        const mentalAdvice = computed(() => {
            const advice = {
                calm: "保持当前节奏，给自己留出一段不被打扰的时间。",
                good: "把充足的精力用在一件重要的小事上，完成后及时肯定自己。",
                tired: "今天降低安排密度，先补水、放松肩颈，再决定是否进行高强度训练。",
                anxious: "试试 4-6 呼吸法：吸气 4 秒，呼气 6 秒，持续 2 分钟。",
                low: "先完成一件最小的照顾自己的行动，也可以找可信任的人聊一聊。",
            };
            return advice[mentalMood.value] || "选一个最接近此刻状态的情绪，开始一次简短的自我觉察。";
        });

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
            loadSocialCenter();
        }

        async function loadSocialCenter() {
            socialLoading.value = true;
            socialError.value = "";
            try {
                socialData.value = await request("/api/social/summary");
                socialUnread.value = socialData.value.unread || { followers: 0, messages: 0, notifications: 0 };
            } catch (requestError) {
                socialError.value = requestError.message;
            } finally {
                socialLoading.value = false;
            }
        }

        async function openSocialCenter(tab) {
            profileOpen.value = false;
            if (socialCenterOpen.value && socialTab.value === tab) {
                socialCenterOpen.value = false;
                return;
            }
            socialTab.value = tab;
            socialCenterOpen.value = true;
            await request(`/api/social/read/${tab}`, { method: "POST" });
            socialUnread.value[tab] = 0;
            await loadSocialCenter();
        }

        async function openSocialProfile(userId) {
            socialCenterOpen.value = false;
            activeNav.value = "community";
            await openCommunityProfile(userId);
        }

        async function openSocialConversation(userId) {
            socialCenterOpen.value = false;
            activeNav.value = "community";
            await openCommunityProfile(userId);
            await openPrivateMessage();
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

        async function openPrivateMessage() {
            privateMessageUser.value = communityProfile.value?.user || null;
            privateMessageDraft.value = "";
            privateMessageReply.value = null;
            clearPrivateImage();
            privateEmojiOpen.value = false;
            privateMessages.value = [];
            privateMessageError.value = "";
            if (!privateMessageUser.value) return;
            privateMessageLoading.value = true;
            try {
                const result = await request(`/api/messages/${privateMessageUser.value.id}`);
                privateMessages.value = result.messages;
            } catch (requestError) {
                privateMessageError.value = requestError.message;
            } finally {
                privateMessageLoading.value = false;
            }
        }

        function closePrivateMessage() {
            privateMessageUser.value = null;
            privateMessageDraft.value = "";
            privateMessages.value = [];
            privateMessageError.value = "";
            privateMessageReply.value = null;
            clearPrivateImage();
            privateEmojiOpen.value = false;
        }

        function quotePrivateMessage(message) {
            privateMessageReply.value = message;
            privateMessageDraft.value = "";
        }

        function selectPrivateImage(event) {
            const file = event.target.files[0];
            if (!file) return;
            if (file.size > 10 * 1024 * 1024) {
                privateMessageError.value = "图片不能超过 10MB";
                return;
            }
            privateImageFile.value = file;
            privateImagePreview.value = URL.createObjectURL(file);
            privateMessageError.value = "";
        }

        function clearPrivateImage() {
            privateImageFile.value = null;
            privateImagePreview.value = "";
        }

        function appendPrivateEmoji(emoji) {
            privateMessageDraft.value += emoji;
            privateEmojiOpen.value = false;
        }

        async function sendPrivateMessage() {
            const content = privateMessageDraft.value.trim();
            if ((!content && !privateImageFile.value) || !privateMessageUser.value || privateMessageSending.value) return;
            privateMessageSending.value = true;
            privateMessageError.value = "";
            try {
                const body = privateImageFile.value ? new FormData() : JSON.stringify({
                    content,
                    reply_to_id: privateMessageReply.value?.id || "",
                    reply_content: privateMessageReply.value?.content || "",
                });
                if (privateImageFile.value) {
                    body.append("content", content);
                    body.append("image", privateImageFile.value);
                    if (privateMessageReply.value) {
                        body.append("reply_to_id", privateMessageReply.value.id);
                        body.append("reply_content", privateMessageReply.value.content || "图片");
                    }
                }
                const result = await request(`/api/messages/${privateMessageUser.value.id}`, { method: "POST", body });
                privateMessages.value.push(result.message);
                privateMessageDraft.value = "";
                privateMessageReply.value = null;
                clearPrivateImage();
                privateEmojiOpen.value = false;
            } catch (requestError) {
                privateMessageError.value = requestError.message;
            } finally {
                privateMessageSending.value = false;
            }
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

        function saveMentalCheckin() {
            if (!mentalMood.value) return;
            localStorage.setItem("movewell-mental-mood", mentalMood.value);
            localStorage.setItem("movewell-mental-checkin", new Date().toISOString());
            mentalCheckinSaved.value = true;
        }

        function planStorageKey(key) {
            return `movewell-plan-${new Date().toISOString().slice(0, 10)}-${key}`;
        }

        function isPlanItemDone(key) {
            return localStorage.getItem(planStorageKey(key)) === "1";
        }

        function togglePlanItem(key) {
            const storageKey = planStorageKey(key);
            if (isPlanItemDone(key)) localStorage.removeItem(storageKey);
            else localStorage.setItem(storageKey, "1");
            planVersion.value += 1;
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

        function openSettings() {
            profileOpen.value = false;
            securityOpen.value = false;
            settingsPage.value = "root";
            passwordForm.value = { current_password: "", new_password: "", confirm_password: "" };
            passwordError.value = "";
            passwordSuccess.value = "";
            settingsOpen.value = true;
        }

        function openSettingsPage(page) {
            settingsPage.value = page;
            securityOpen.value = page === "security";
        }

        function backSettingsPage() {
            settingsPage.value = "root";
            securityOpen.value = false;
        }

        function saveSettingsPreference(key, value, storageKey) {
            const current = key === "notification" ? notificationSettings.value : privacySettings.value;
            const next = { ...current, ...value };
            localStorage.setItem(storageKey, JSON.stringify(next));
            if (key === "notification") notificationSettings.value = next;
            if (key === "privacy") privacySettings.value = next;
        }

        function chooseDisplayMode(mode) {
            displayMode.value = mode;
            localStorage.setItem("movewell-display-mode", mode);
            if (mode === "care") fontScale.value = "large";
            document.body.classList.toggle("care-mode", mode === "care");
            document.body.classList.toggle("large-text-mode", fontScale.value === "large");
            localStorage.setItem("movewell-font-scale", fontScale.value);
        }

        function chooseFontScale(scale) {
            fontScale.value = scale;
            localStorage.setItem("movewell-font-scale", scale);
            document.body.classList.toggle("large-text-mode", scale === "large");
        }

        function openAccountSecurity() {
            securityOpen.value = true;
            passwordError.value = "";
            passwordSuccess.value = "";
        }

        function closeAccountSecurity() {
            backSettingsPage();
            passwordError.value = "";
            passwordSuccess.value = "";
        }

        function toggleDarkMode() {
            darkMode.value = !darkMode.value;
            document.body.classList.toggle("dark-mode", darkMode.value);
            localStorage.setItem("movewell-dark-mode", darkMode.value ? "1" : "0");
            if (darkMode.value) displayMode.value = "night";
            localStorage.setItem("movewell-display-mode", displayMode.value);
        }

        async function updatePassword() {
            passwordSaving.value = true;
            passwordError.value = "";
            passwordSuccess.value = "";
            try {
                await request("/api/password", {
                    method: "POST",
                    body: JSON.stringify(passwordForm.value),
                });
                passwordForm.value = { current_password: "", new_password: "", confirm_password: "" };
                passwordSuccess.value = "密码修改成功，下次登录请使用新密码。";
            } catch (requestError) {
                passwordError.value = requestError.message;
            } finally {
                passwordSaving.value = false;
            }
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
            if (file.size > 10 * 1024 * 1024) {
                profileError.value = "头像图片不能超过 10MB";
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
            settingsOpen,
            securityOpen,
            settingsPage,
            darkMode,
            displayMode,
            fontScale,
            notificationSettings,
            privacySettings,
            passwordForm,
            passwordSaving,
            passwordError,
            passwordSuccess,
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
            mentalMood,
            mentalCheckinSaved,
            mentalMoods,
            mentalRecoveryScore,
            mentalStatus,
            mentalAdvice,
            saveMentalCheckin,
            openSettings,
            openSettingsPage,
            backSettingsPage,
            openAccountSecurity,
            closeAccountSecurity,
            saveSettingsPreference,
            chooseDisplayMode,
            chooseFontScale,
            toggleDarkMode,
            updatePassword,
            planItems,
            planCompletedCount,
            planProgress,
            isPlanItemDone,
            togglePlanItem,
            communityPosts,
            communityContent,
            communityError,
            communitySaving,
            communityComments,
            communityDrafts,
            communityCommentOpen,
            communityProfile,
            privateMessageUser,
            privateMessageDraft,
            privateMessages,
            privateMessageLoading,
            privateMessageSending,
            privateMessageError,
            privateMessageReply,
            privateImagePreview,
            privateEmojiOpen,
            privateEmojis,
            socialCenterOpen,
            socialTab,
            socialLoading,
            socialError,
            socialData,
            socialUnread,
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
            openPrivateMessage,
            closePrivateMessage,
            sendPrivateMessage,
            quotePrivateMessage,
            selectPrivateImage,
            clearPrivateImage,
            appendPrivateEmoji,
            openSocialCenter,
            openSocialProfile,
            openSocialConversation,
            toggleCommunityFollow,
            toggleExerciseHistory,
            filterExerciseHistory,
            clearExerciseFilters,
        };
    },
}).mount("#app");
