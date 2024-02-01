import requests
import json
import os
import s3fs
import pyspark
from pyspark.sql import SparkSession
from pyspark import SparkContext
import pyspark.sql.functions as F
# Define environment variables
os.environ["MINIO_KEY"] = "minio"
os.environ["MINIO_SECRET"] = "minio123"
os.environ["MINIO_ENDPOINT"] = "http://192.168.1.101:9000"


# Get data using REST API
def fetch_countries_data(url):
    # Using session is particularly beneficial 
    # if you are making multiple requests to the same server, 
    # as it can reuse the underlying TCP connection, 
    # leading to performance improvements.
    with requests.Session() as session:
        response = session.get(url)
        response.raise_for_status()
        
        if response.status_code == 200:
            return response.json()
        else:
            return f"Error: {response.status_code}"

# Fetch data
countries_data = fetch_countries_data("https://restcountries.com/v3.1/all")


# Write data to minIO as a JSON file

fs = s3fs.S3FileSystem(
    client_kwargs={'endpoint_url': os.environ["MINIO_ENDPOINT"]}, # minio1 = minio container name
    key=os.environ["MINIO_KEY"],
    secret=os.environ["MINIO_SECRET"],
    use_ssl=False  # Set to True if MinIO is set up with SSL
)

with fs.open('mybucket/country_data.json', 'w', encoding='utf-8') as f:
    json.dump(countries_data,f)

spark = SparkSession.builder \
    .appName("country_data_analysis") \
    .master("spark://192.168.1.101:7077") \
    .config("spark.jars.packages", "org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.11.1026") \
    .config("spark.hadoop.fs.s3a.endpoint", os.environ["MINIO_ENDPOINT"]) \
    .config("spark.hadoop.fs.s3a.access.key", os.environ["MINIO_KEY"]) \
    .config("spark.hadoop.fs.s3a.secret.key", os.environ["MINIO_SECRET"]) \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .enableHiveSupport() \
    .getOrCreate()
    
    # Check PySpark version
print("pyspark version:", pyspark.__version__)

# Check Hadoop version
sc = SparkContext.getOrCreate()
hadoop_version = sc._gateway.jvm.org.apache.hadoop.util.VersionInfo.getVersion()
print("Hadoop version:", hadoop_version)
    
# Read JSON data using PySpark
df = spark.read.option("inferSchema",True).json("s3a://mybucket/country_data.json")
# Returns count of rows in the dataframe
df.count() 


# Write same data as Parquet and re-read in dataframe
df.write.mode("overwrite").format("parquet").save("s3a://mybucket/country_raw_data.parquet")
country_raw_data = spark.read.parquet("s3a://mybucket/country_raw_data.parquet")
country_raw_data.count()

# Perform transformations to raw data
country_trnsfm_data = (
    country_raw_data
    .selectExpr(
        "name.common as cntry_name",
        "area as cntry_area",
        "borders as border_cntry",
        "capital as capital_cities",
        "continents as cntry_continent",
        "landlocked as is_landlocked",
        "population",
        "startOfWeek",
        "timezones as nr_timezones",
        "unMember as is_unmember"
    )
    .withColumn("cntry_area",F.when(F.col("cntry_area") < 0, None).otherwise(F.col("cntry_area")))
    .withColumn("border_cntry",F.when(F.col("border_cntry").isNull(),F.array(F.lit("NA"))).otherwise(F.col("border_cntry")))
    .withColumn("capital_cities",F.when(F.col("capital_cities").isNull(),F.array(F.lit("NA"))).otherwise(F.col("capital_cities")))    
)

# Print schema of transformed data
country_trnsfm_data.printSchema()

# Create external hive table using PARQUET
spark.sql("""
CREATE EXTERNAL TABLE country_data (
    cntry_name STRING,
    cntry_area DOUBLE,
    border_cntry ARRAY<STRING>,
    capital_cities ARRAY<STRING>,
    cntry_continent ARRAY<STRING>,
    is_landlocked BOOLEAN,
    population BIGINT,
    startOfWeek STRING,
    nr_timezones ARRAY<STRING>,
    is_unmember BOOLEAN
)
STORED AS PARQUET
LOCATION 's3a://mybucket/country_trnsfm_data.parquet';
""").show()


# Show table details
spark.sql("DESCRIBE EXTENDED default.country_data").show(100,truncate = False)


 # Show first 5 records from the table
spark.sql("SELECT * FROM default.country_data LIMIT 5").show(truncate = False)

# Create temporary view using dataframe
spark.table("default.country_data").createOrReplaceTempView("country_data_processed_view")


# Function to show Spark SQL results
def show_results(sql_string):
    
    
    
    return spark.sql(
        sql_string
    ).show(truncate = False)   
    
    
# 1. Which are the 10 largest countries in terms of area? (in sq. km.)
sql_string = """
    SELECT cntry_name, cntry_area
    FROM country_data_processed_view
    ORDER BY cntry_area DESC
    LIMIT 10
    """
show_results(sql_string)


# 2. Which country has the largest number of neighbouring countries?
sql_string = """
    SELECT cntry_name, border_cntry, array_size(border_cntry) as ngbr_cntry_nr
    FROM country_data_processed_view
    WHERE NOT array_contains(border_cntry,'NA')
    ORDER BY array_size(border_cntry) DESC
    LIMIT 1
    """
show_results(sql_string)


# 3. Which countries have the highest number of capital cities?
sql_string = """
    SELECT cntry_name, capital_cities, array_size(capital_cities) as total_capital_cities
    FROM country_data_processed_view
    WHERE NOT array_contains(capital_cities,'NA')
    ORDER BY array_size(capital_cities) DESC
    LIMIT 2
    """
show_results(sql_string)


# 4. How many countries lie on two or more continents?
sql_string = """
    SELECT cntry_name, cntry_continent, array_size(cntry_continent) as total_continents
    FROM country_data_processed_view
    ORDER BY array_size(cntry_continent) DESC
    LIMIT 3
    """
show_results(sql_string)


# 5. How many landlocked countries per continent?
sql_string = """
    SELECT continent, SUM(is_landlocked) as landlocked_nr
    FROM (SELECT cntry_name, case when is_landlocked then 1 else 0 end as is_landlocked, explode(cntry_continent) as continent
    FROM country_data_processed_view)
    GROUP BY continent
    ORDER BY SUM(is_landlocked) DESC
    """
show_results(sql_string)

# 6. Which country has the highest number of time zones?
sql_string = """
    SELECT cntry_name, nr_timezones, array_size(nr_timezones) as total_timezones
    FROM country_data_processed_view
    ORDER BY array_size(nr_timezones) DESC
    LIMIT 1
    """
show_results(sql_string)


# 7. How many countries are not UN members?
sql_string = """
    SELECT COUNT(*) AS count
    FROM country_data_processed_view
    WHERE NOT is_unmember
    """
show_results(sql_string)

