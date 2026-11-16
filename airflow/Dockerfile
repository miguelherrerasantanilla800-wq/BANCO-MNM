FROM apache/hadoop:3.3.6 AS hadoop

FROM apache/airflow:2.9.3-python3.11

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=hadoop /opt/hadoop /opt/hadoop
COPY hadoop/core-site.xml hadoop/hdfs-site.xml hadoop/yarn-site.xml hadoop/mapred-site.xml /opt/hadoop/etc/hadoop/
COPY --chown=airflow:root airflow/dags/ /opt/airflow/dags/
COPY --chown=airflow:root mapreduce/ /opt/airflow/mapreduce/

ENV HADOOP_HOME=/opt/hadoop \
    HADOOP_CONF_DIR=/opt/hadoop/etc/hadoop \
    JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 \
    PATH=/opt/hadoop/bin:/opt/hadoop/sbin:/usr/lib/jvm/java-17-openjdk-amd64/bin:$PATH

USER airflow
