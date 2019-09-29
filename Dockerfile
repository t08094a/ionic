FROM node:lts

#ARG USER_ID=1000
#ARG GROUP_ID=1000

# map user if --build-args USER_ID und GROUP_ID are set
#RUN if [ ${USER_ID:-0} -ne 0 ] && [ ${GROUP_ID:-0} -ne 0 ]; then \
#        if [ ${USER_ID:-0} -ne 1000 ] && [ ${GROUP_ID:-0} -ne 1000 ]; then \
#            groupadd -g ${GROUP_ID} newuser && \
#            useradd --disable-password --no-log-init -r -u ${USER_ID} -g newuser -m /bin/bash newuser \
#        ;fi \
#    ;fi

# ENVIRONNEMENT
ENV GRADLE_HOME=/opt/gradle \
    GRADLE_VERSION=5.6.2 \
    \
    JAVA_HOME=/usr/lib/jvm/java-1.8.0-openjdk-amd64 \
    # Android 10
    SDK_URL="https://dl.google.com/android/repository/sdk-tools-linux-4333796.zip" \
    ANDROID_HOME="/usr/local/android-sdk" \
    ANDROID_VERSION=29 \ 
    ANDROID_BUILD_TOOLS_VERSION=29.0.2

# INSTALL JAVA, python libs, create dir and cleanup apt
RUN apt-get update -y && \
    apt-get full-upgrade -y && \
    apt-get -y install locales locales-all vim && \
    apt-get install -y openjdk-8-jdk openjdk-8-jre && \
    apt-get install -y python3 python3-pip && \
    echo "set locale settings" && \
    locale-gen de_DE.UTF-8 && \
    update-locale LANG=de_DE.UTF-8 LANGUAGE LC_ALL && \
    pip3 install inquirer colorama && \
    rm -rf /lib/apt/listspt/lists/*

ENV PATH=/docker_tools:${GRADLE_HOME}/bin:${JAVA_HOME}/bin:${ANDROID_HOME}/tools/bin:${ANDROID_HOME}/platform-tools:${ANDROID_HOME}/build-tools:${ANDROID_HOME}/emulator:${PATH} \
    HOME=/home/node \
    LANG=de_DE.UTF8 \
    LANGUAGE=de \
    LC_ALL=de_DE.UTF8

#RUN update-java-alternatives -l
#RUN echo $JAVA_HOME && ${JAVA_HOME}/bin/java -version

# INSTALL IONIC AND CORDOVA and correct the permissions to user 'node'
RUN npm install -g ionic cordova && \
    chown -R node:node /home/node/.config && \
    chown -R node:node /home/node/.npm

# INSTALL Graddle
RUN mkdir -p ${GRADLE_HOME} && \
    curl -L https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip > /tmp/gradle.zip && \
    unzip /tmp/gradle.zip -d ${GRADLE_HOME} && \
    mv ${GRADLE_HOME}/gradle-${GRADLE_VERSION}/* ${GRADLE_HOME} && \
    rm -r ${GRADLE_HOME}/gradle-${GRADLE_VERSION}/ && \
    rm /tmp/gradle.zip

# Download Android SDK
RUN mkdir ${ANDROID_HOME} /root/.android \
    && touch /root/.android/repositories.cfg \
    && cd ${ANDROID_HOME} \
    && curl -o sdk.zip $SDK_URL \
    && unzip sdk.zip \
    && rm sdk.zip

# Install Android Build Tool and Libraries
RUN ${ANDROID_HOME}/tools/bin/sdkmanager --update && \
    yes | ${ANDROID_HOME}/tools/bin/sdkmanager --licenses && \
    ${ANDROID_HOME}/tools/bin/sdkmanager "build-tools;${ANDROID_BUILD_TOOLS_VERSION}" \
    "platforms;android-${ANDROID_VERSION}" \
    "platform-tools"

ADD ./docker_tools/runner.py /docker_tools/

EXPOSE 8100 35729
CMD ["/docker_tools/runner.py"]
