# It's a Mistral Docker image. You should use the Mistral version 5.1.0 and more.
FROM dp-mistral

USER root

# An your source of actions will be here
ENV CUSTOM_ACTIONS_SOURCE_FOLDER="/opt/test-actions"
# Change to root user to avoid a problems with verivication of the Linux rights

ADD requirements.txt "${CUSTOM_ACTIONS_SOURCE_FOLDER}/requirements.txt"
RUN pip install -r "${CUSTOM_ACTIONS_SOURCE_FOLDER}/requirements.txt"

# Add source of your action to the Mistral image
ADD . "${CUSTOM_ACTIONS_SOURCE_FOLDER}"
# Install the your library with Mistral actions
RUN pip install --no-dependencies --no-cache-dir -e "${CUSTOM_ACTIONS_SOURCE_FOLDER}"