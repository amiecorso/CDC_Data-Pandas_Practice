'''
Author: Amie Corso
Practice with Python's Pandas and GeoPandas libraries
processes the CDC's dataset "U.S. Chronic Disease Indicators" found at the following URL:
https://catalog.data.gov/dataset/u-s-chronic-disease-indicators-cdi-e50c9

Calculates and writes to file correlations between each specific health data question, and 2016 election results.
Processes county-level election data to create aggregate state-level election data.
Manipulates raw health data to add associated election data and also adds Shapely objects (Polygons) for use in creating
 chloropleth graphs using GeoPandas.
'''

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

# DATA
votes_fp = "./Datasets/2016_US_County_Level_Presidential_Results.csv"  # election data
health_fp = "./Datasets/U.S._Chronic_Disease_Indicators__CDI_.csv"     # CDC health data
#health_fp = "./Datasets/HEALTHDATA_SHORT.csv"  # short dataset for speedup
states_fp = "./Datasets/tl_2017_us_state/tl_2017_us_state.shp"  # shapefile for state polygons

# HEALTH DATA
healthdata = pd.read_csv(health_fp, encoding="latin-1", low_memory=False)
states_gdf = gpd.read_file(states_fp)  # geodataframe of state data/shapes
# clean health data
columns = healthdata.columns
# examine for columns that contain useless data
useless_cols = ["DataValueFootnoteSymbol", "TopicID", "QuestionID", "DataValueTypeID", "StratificationCategoryID1", "StratificationID1"]
for column in columns:
    unique_vals = list(healthdata[column].unique())
    if len(unique_vals) < 3:
        useless_cols.append(column)
# remove useless columns from dataframe
healthdata.drop(useless_cols, inplace=True, axis=1)

# convert data to correct datatypes (invalid conversions will become NaN)
healthdata["DataValue"] = pd.to_numeric(healthdata.DataValue, errors="coerce")
#print(healthdata.dtypes)

# VOTE DATA
votedata = pd.read_csv(votes_fp)
grouped = votedata.groupby("state_abbr")
# Collapse counties
grouped = votedata.groupby(['state_abbr'], as_index=False).sum()

# recalculate percentages
grouped.drop(["per_dem", "per_gop", "combined_fips"], inplace=True, axis=1)
per_dem = (grouped['votes_dem'] / grouped['total_votes']) * 100
per_gop = (grouped['votes_gop'] / grouped['total_votes']) * 100
grouped['per_dem'] = per_dem
grouped['per_gop'] = per_gop

# ADD VOTE DATA TO HEALTH DATA
voteDict = {}
states = grouped['state_abbr'] # state series
for i in range(len(states)):
    voteDict[states[i]] = (grouped["per_dem"][i], grouped["per_gop"][i])

#print("VOTE DICT: ", voteDict)
per_dems = {}
per_gops = {}
for index, row in healthdata.iterrows():
    try:
        per_dems[index] = voteDict[row["LocationAbbr"]][0] # grab the democratic part of tuple
        per_gops[index] = voteDict[row["LocationAbbr"]][1] # grab the gop part of tuple
    except KeyError:
        per_dems[index] = None
        per_gops[index] = None

# add the correct series to master health dataframe
healthdata.loc[:,"per_dem"] = pd.Series(per_dems, index=healthdata.index)
healthdata.loc[:,"per_gop"] = pd.Series(per_gops, index=healthdata.index)

# ADD GEOMETRIES
# associate each entry with shapely polygon from state data
stateseries = states_gdf["STUSPS"]   #associate state abbreviations and their geometries
shapeseries = states_gdf["geometry"]
stateDict = {}                          # collect associations into a dictionary
for i in range(len(stateseries)):
    stateDict[stateseries[i]] = shapeseries[i]
# iterate through every row in DataFrame (healthdata)
# grab the state abbreviation, store associated geometry (index aligned)
geometries = {}
for index, row in healthdata.iterrows():
    try:
        geometries[index] = stateDict[row["LocationAbbr"]]
    except KeyError:
        geometries[index] = None  # None is an acceptable value for the absence of a geometry in geopandas

# turn this index:shape dictionary into a pandas series
geometry = pd.Series(geometries, index=healthdata.index)
crs = {'init': 'epsg:4269'} # need correct coordinate ref system for our GeoDataFrame

# CREATE A GEODATAFRAME from original pandas DataFrame and newly created geometry series
healthdata_gdf = gpd.GeoDataFrame(healthdata, crs=crs, geometry=geometry)


# take a look at available questions:
QUESTIONS = list(healthdata_gdf.Question.unique())
CORRELATIONS = [] # collect results

# PROCESS ALL QUESTIONS
for question in QUESTIONS:
    sub_gdf = healthdata_gdf.loc[healthdata_gdf['Question'] == question]
    sub_gdf = sub_gdf.loc[sub_gdf["Stratification1"] == "Overall"] # don't separate based on ethnicity or gender
    correlation = sub_gdf["DataValue"].corr(sub_gdf["per_gop"]) # calculate the correlation with votes
    units_mode = sub_gdf.DataValueUnit.mode() # get unit of measure, regardless of potential inconsistencies
    if len(units_mode) > 0: # if there was actual data for this question
        units = units_mode[0]
        CORRELATIONS.append((question, units, correlation, sub_gdf))
        # store a tuple of values for later use, including the sub_geodataframe
    else: # if there was no actual data for this question
        units = "???"

CORRELATIONS.sort(key=lambda x: x[2])

# WRITE TO OUTPUT
with open("./correlations_output", 'w') as output:
    output.write("Correlation coeffecients between CDC health data questions and percentage of Republican votes on a state-by-state basis\n\n")
    for entry in CORRELATIONS:
        qstring = entry[0] + " (" + entry[1] + ")"
        qstring = "{:_<200}".format(qstring)
        output.write(qstring)
        if type(entry[2]) == float:
            output.write(str(round(entry[2], 3)) + '\n')
        else:
            output.write(str(entry[2]) + '\n')

# GENERATE PLOTS
entry = CORRELATIONS[0]
to_plot = entry[3] # the last one in the list = highest correlation

print(to_plot) # double-check data to be plotted

fig, ax = plt.subplots()
ax.set_aspect('equal')
ax.set_xlim([-180, -60]) # set bounding box around U.S.
ax.set_ylim([20, 75])
fig.suptitle(entry[0] + " (" + entry[1] + ")", fontsize=14)
#fig.suptitle("Democratic votes (%)", fontsize = 14)
# plot the map on THESE axes, based on the attribute in column, using cmap color scheme (see matplotlib for color schemes)
to_plot.plot(ax=ax, column="DataValue", cmap="Purples", legend=True)
#to_plot.plot(ax=ax, column="per_dem", cmap="Blues", legend=True)
plt.show()