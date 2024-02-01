FROM python:3.11.4-buster as builder

RUN apt-get -y update
RUN apt-get -y upgrade
RUN apt-get -y install tree
ENV PIPENV_VENV_IN_PROJECT=1

# ENV PIPENV_VENV_IN_PROJECT=1 is important: it causes the resuling virtual environment to be created as /app/.venv. Without this the environment gets created somewhere surprising, such as /root/.local/share/virtualenvs/app-4PlAip0Q - which makes it much harder to write automation scripts later on.

RUN python -m pip install --upgrade pip
RUN pip install --no-cache-dir pipenv
RUN pip install --no-cache-dir jupyter
RUN pip install --no-cache-dir py4j
RUN pip install --no-cache-dir findspark

#############################################
# install java and spark and hadoop
# Java is required for scala and scala is required for Spark
############################################

# VERSIONS

ENV SPARK_VERSION=3.5.0 \
HADOOP_VERSION=3.3.4 \
SPARK_HOME=/opt/spark \
PYTHONHASHSEED=1 \
JAVA_VERSION=11

RUN apt-get update --yes && \
    apt-get install --yes --no-install-recommends \
    "openjdk-${JAVA_VERSION}-jre-headless" \
    ca-certificates-java  \
    vim \
    wget \
    ssh \
    net-tools \
    ca-certificates \
    curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*


# Add Dependencies for PySpark
#RUN apt-get install -yes vim wget software-properties-common ssh net-tools ca-certificates  python3-pip python3-numpy python3-matplotlib python3-scipy python3-pandas python3-simpy

RUN java --version

RUN update-alternatives --install "/usr/bin/python" "python" "/usr/local/bin/python3.11" 1
RUN ln -s /usr/local/bin/python3.11 /usr/bin/python3.11

RUN wget --no-verbose -O apache-spark.tgz "https://archive.apache.org/dist/spark/spark-3.5.0/spark-3.5.0-bin-hadoop3.tgz" \
&& mkdir -p /opt/spark \
&& tar -xf apache-spark.tgz -C /opt/spark --strip-components=1 \
&& rm apache-spark.tgz


FROM builder as apache-spark

WORKDIR /opt/spark

ENV SPARK_MASTER_PORT=7077 \
SPARK_MASTER_WEBUI_PORT=8080 \
SPARK_LOG_DIR=/opt/spark/logs \
SPARK_MASTER_LOG=/opt/spark/logs/spark-master.out \
SPARK_WORKER_LOG=/opt/spark/logs/spark-worker.out \
SPARK_WORKER_WEBUI_PORT=8080 \
SPARK_WORKER_PORT=7000 \
SPARK_MASTER="spark://spark-master:7077" \
SPARK_WORKLOAD="master"

EXPOSE 8080 7077 7000

RUN mkdir -p $SPARK_LOG_DIR && \
touch $SPARK_MASTER_LOG && \
touch $SPARK_WORKER_LOG && \
ln -sf /dev/stdout $SPARK_MASTER_LOG && \
ln -sf /dev/stdout $SPARK_WORKER_LOG

COPY start-spark.sh /

CMD ["/bin/bash", "/start-spark.sh"]