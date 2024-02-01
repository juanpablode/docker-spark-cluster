import sys
from random import random
from operator import add


from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, IntegerType


# Configura la sesión de Spark
spark = SparkSession.builder \
        .appName("EjemploSparkSQL2") \
        .master("spark://192.168.1.101:7077") \
        .enableHiveSupport() \
        .getOrCreate()
        
# Crea una tabla de ejemplo
schema = StructType([
       StructField("id", IntegerType(), True),
       StructField("nombre", StringType(), True)
    ])

data = [(1, "Ejemplo1"), (2, "Ejemplo2"), (3, "Ejemplo3")]
rdd = spark.sparkContext.parallelize(data)
df = spark.createDataFrame(rdd, schema=schema)

# Registra la tabla como una vista temporal
df.createOrReplaceTempView("ejemplo_table")

# Realiza una consulta para contar los elementos de la tabla
count_result = spark.sql("SELECT COUNT(*) AS count FROM ejemplo_table").collect()

# Imprime el resultado
print("Conteo de elementos: {}".format(count_result[0]["count"]))

spark.stop()