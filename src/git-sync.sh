# Функция настраивает глобальные параметры git,
# актуальные как для src, так и для dst
set_git_global_settings() {
    echo -e "\033[1;35m|\033[1;36m [INFO] Git global settings set.\033[0m"
    # git config --global http.postBuffer 2097152000
    # git config --global http.postBuffer 2097152000
    # git config --global http.sslbackend schannel
}



### SETUP src
set_src_git() {
    src_git_url=$(yq '.git_config.src.url' $config_name)
    src_git_proxy=$(yq '.git_config.src.proxy' $config_name)
    src_git_auth_type=$(yq '.git_config.src.auth.type' $config_name)

    if [[ "$src_git_auth_type" -eq "oauth2" ]]; then
        src_git_auth_token=$(yq '.git_config.src.auth.token' $config_name)
        src_git_url=$(make_oauth2_url $src_git_url $src_git_auth_token)
    fi
}



### SETUP dst
set_dst_git() {
    dst_git_url=$(yq '.git_config.dst.url' $config_name)
    dst_git_proxy=$(yq '.git_config.dst.proxy' $config_name)
    dst_git_auth_type=$(yq '.git_config.dst.auth.type' $config_name)

    if [[ "$dst_git_auth_type" -eq "oauth2" ]]; then
        dst_git_auth_token=$(yq '.git_config.dst.auth.token' $config_name)
        dst_git_url=$(make_oauth2_url $dst_git_url $dst_git_auth_token)
    fi
}



# Функция встраивает в url oauth2 и token.
# Вызывать только после проверки auth.type = oauth2
make_oauth2_url() {
    local url="$1"
    local token="$2"
    local scheme=${url%%://*}
    local no_scheme=${url##*://}
    echo "$scheme://oauth2:$token@$no_scheme"
}



# Функция клонирует репозиторий с пересозданием.
# Принимает url гита, subgroups и имя репозитория как аргументы.
clone_repo() {
    local git_url=$1
    local path=$2
    local name=$3

    echo -e "\033[1;35m|\033[1;36m [INFO] Git clone.\033[0m"
    
    cd $temp_dir
    rm -rf $temp_dir/$path/$name
    mkdir -p $temp_dir/$path

    log=$(git clone ${git_url}/${path}/${name}.git $temp_dir/$path/$name 2>&1)
    if [[ $? -eq 0 ]]; then
        echo -e "\033[1;35m|\033[1;36m [INFO] Local repository \033[1;32msuccessfully\033[1;36m cloned:\033[0m"
        while IFS= read -r line; do
          echo -e "\033[1;35m|\033[1;36m [INFO]\033[1;30m $line\033[0m"
        done <<< "$log"
    else
        echo -e "\033[1;35m|\033[1;31m [ERROR] Error cloning git:\033[0m"
        while IFS= read -r line; do
          echo -e "\033[1;35m|\033[1;31m [ERROR]\033[1;30m $line\033[0m"
        done <<< "$log"
    fi
}



# Функция обновляет отслеживаемые ветки и обновляет,
# забирает все изменения из репозиторий в локальную фс.
# Принимает subgroups и имя репозитория как аргументы.
update_repo() {
    local path=$1
    local name=$2

    echo -e "\033[1;35m|\033[1;36m [INFO] Git update.\033[0m"

    cd $temp_dir/$path/$name

    log=$(
        git branch -r | grep -v '\->' | sed "s,\x1B\[[0-9;]*[a-zA-Z],,g" | while read remote; do git branch --track "${remote#origin/}" "$remote"; done 2>&1
        git fetch --all --prune 2>&1
        git pull --all 2>&1
        git branch -vv | awk '/: gone]/{print $1}' | xargs git branch -D 2>&1
        for b in `git branch -r | grep -v -- '->'`; do
            git checkout ${b##origin/} 2>&1
            git pull 2>&1
        done
        git fetch --tags --prune-tags 2>&1
        git pull --tags 2>&1
    )
    if [[ $? -eq 0 ]]; then
        echo -e "\033[1;35m|\033[1;36m [INFO] Local repository \033[1;32msuccessfully\033[1;36m updated:\033[0m"
        while IFS= read -r line; do
          echo -e "\033[1;35m|\033[1;36m [INFO]\033[1;30m $line\033[0m"
        done <<< "$log"
    else
        echo -e "\033[1;35m|\033[0;33m [WARNING] Local repository update error:\033[0m"
        while IFS= read -r line; do
          echo -e "\033[1;35m|\033[0;33m [WARNING]\033[1;30m $line\033[0m"
        done <<< "$log"
        clone_repo $src_git_url $path $name
    fi
}



# Функция устанавливает/удаляет прокси.
# Принимает url-proxy как аргумент
set_proxy() {
    local proxy=$1
    if [[ "$proxy" == "null" ]]; then
        git config --global --unset http.proxy
        echo -e "\033[1;35m|\033[1;36m [INFO] Proxy unset.\033[0m"
    else
        git config --global http.proxy $proxy
        echo -e "\033[1;35m|\033[1;36m [INFO] Proxy set: $proxy.\033[0m"
    fi
}



# Функция выборки веток для синхронизации.
# Выбирает include_branches, иначе все ветки
# минуc exclude_branches.
# Принимает subgroups и имя репозитория как аргументы.
selecting_branches() {
    local path=$1
    local name=$2

    echo -e "\033[1;35m|\033[1;36m [INFO] Selecting branches.\033[0m"

    cd $temp_dir/$path/$name

    selected_branches=()

    local include_branches=()
    readarray include_branches < <(yq '.repos.[] | select(.name == env(REPO))| .include_branches.[] ' $config_name)

    if [[ ${#include_branches[@]} -eq 0 ]]; then
        local all_branches=()
        mapfile -t all_branches <<< "$(git branch --list | cut -c 3-)"
        local exclude_branches=()
        readarray exclude_branches < <(yq '.repos.[] | select(.name == env(REPO))| .exclude_branches.[] ' $config_name)

        for branch in "${exclude_branches[@]}"; do
            branch=${branch%$'\n'}   # Remove a trailing newline.
            for i in "${!all_branches[@]}"; do
                if [[ ${all_branches[i]} = $branch ]]; then
                    unset 'all_branches[i]'
                fi
            done
        done
        selected_branches=("${all_branches[@]}")
    else
        for branch in "${include_branches[@]}"; do
            branch=${branch%$'\n'}   # Remove a trailing newline.
            selected_branches+=("$branch")
        done
    fi
}



# Функция пушит локальный репозиторий в dst-гит.
# Учитываем sync_tags (пушить все теги или нет)
# Принимает url гита, subgroups и имя репозитория как аргументы.
push_repo() {
    local git_url=$1
    local path=$2
    local name=$3
    local selected_branches=("${selected_branches[@]}")

    echo -e "\033[1;35m|\033[1;36m [INFO] Git push: '$temp_dir/$path/$name'.\033[0m"

    cd $temp_dir/$path/$name

    git remote add ext ${git_url}/${path}/${name}.git 2>/dev/null

    branche_iter=0
    number_branches=${#selected_branches[@]}

    for branch in "${selected_branches[@]}"; do
        branche_iter=$((branche_iter + 1))
        echo -e "\033[1;35m|\033[1;36m [INFO] Pushing a branch: $branch [$branche_iter/$number_branches]\033[0m"
        allow_force_push=$(yq '.allow_force_push' $config_name)
        if [[ "$allow_force_push" -eq "true" ]]; then
            log=$(git push ext --force $branch 2>&1)
        else
            log=$(git push ext $branch 2>&1)
        fi
        if [[ $? -eq 0 ]]; then
            echo -e "\033[1;35m|\033[1;36m [INFO] Branch '$branch' \033[1;32msuccessfully\033[1;36m pushed:\033[0m"
            while IFS= read -r line; do
              echo -e "\033[1;35m|\033[1;36m [INFO]\033[1;30m $line\033[0m"
            done <<< "$log"
        elif [[ $? -eq 128 ]]; then
            echo -e "\033[1;35m|\033[1;31m [ERROR] Please, create repository or add access: $path/$name. Error:\033[0m"
            while IFS= read -r line; do
              echo -e "\033[1;35m|\033[1;31m [ERROR]\033[1;30m $line\033[0m"
            done <<< "$log"
            break
        else
            echo -e "\033[1;35m|\033[1;31m [ERROR] Error pushing to remote repository: $path/$name. Error:\033[0m"
            while IFS= read -r line; do
              echo -e "\033[1;35m|\033[1;31m [ERROR]\033[1;30m $line\033[0m"
            done <<< "$log"
        fi
    done

    # push tags
    local sync_tags=$(yq '.repos.[] | select(.name == env(REPO))| .sync_tags ' $config_name) # read sync_tags from config [repos.{REPO}.sync_tags]

    if [[ "$sync_tags" = "true" ]]; then
        echo -e "\033[1;35m|\033[1;36m [INFO] Pushing all tags.\033[0m"
        log=$(git push ext --force --tags 2>&1)
        if [[ $? -eq 0 ]]; then
            echo -e "\033[1;35m|\033[1;36m [INFO] All tags \033[1;32msuccessfully\033[1;36m pushed:\033[0m"
            while IFS= read -r line; do
              echo -e "\033[1;35m|\033[1;36m [INFO]\033[1;30m $line\033[0m"
            done <<< "$log"
        elif [[ $? -eq 128 ]]; then
            echo -e "\033[1;35m|\033[1;31m [ERROR] Please, create repository or add access: $path/$name. Error:\033[0m"
            while IFS= read -r line; do
              echo -e "\033[1;35m|\033[1;31m [ERROR]\033[1;30m $line\033[0m"
            done <<< "$log"
            break
        fi
    else
        echo -e "\033[1;35m|\033[1;36m [INFO] Pushing tags is skipped because sync_tags: '$sync_tags'.\033[0m"
    fi

    git remote remove ext 2>/dev/null
}



main () {
    ### SETUP base parameters
    config_name=/app/config.yaml
    temp_dir=$(yq '.temp_dir' $config_name)
    readarray repos < <(yq '.repos.[].name' $config_name)
    sleep_seconds=$(yq '.wait_next_run_seconds' $config_name)
    if [[ "$sleep_seconds" = "null" ]]; then
        sleep_seconds=600
    fi
    ### SETUP git env
    set_src_git
    set_dst_git
    
    ### SETUP git global settings
    set_git_global_settings

    ### Base dir
    mkdir -p $temp_dir

    runs_iter=0

    while true; do
        runs_iter=$((runs_iter + 1))
        repo_iter=0
        number_repos=${#repos[@]}

        echo -e "\033[1;35m|\033[1;36m [INFO] \033[1;33mLounch: [$runs_iter]\033[0m"

        for repo in "${repos[@]}"; do
            repo_iter=$((repo_iter + 1))
            bar=$(printf "[%-${number_repos}s]" $(printf "%${repo_iter}s" | tr ' ' '#'))
            export REPO="$repo"
            repo=${repo%$'\n'}   # Remove a trailing newline.
            echo -e "\033[1;35m|\033[1;36m [INFO] \033[1;35mProgress: $bar\033[0m"
            echo -e "\033[1;35m|\033[1;36m [INFO] \033[1;35mRepo: '$repo'.\033[0m"
            repo_path="${repo%/*}"
            repo_name="${repo##*/}"

            set_proxy $src_git_proxy

            if [ -d "$temp_dir/$repo_path/$repo_name" ]; then
                echo -e "\033[1;35m|\033[1;36m [INFO] Repository already exist. Skip clone.\033[0m"
            else
                clone_repo $src_git_url $repo_path $repo_name
            fi

            update_repo $repo_path $repo_name

            selecting_branches $repo_path $repo_name

            set_proxy $dst_git_proxy

            push_repo $dst_git_url $repo_path $repo_name
        done

        echo -e "\033[1;35m|\033[1;36m [INFO] Waiting for the next run: $sleep_seconds seconds.\033[0m"
        sleep $sleep_seconds;
    done
}

main
